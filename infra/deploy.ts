import * as pulumi from '@pulumi/pulumi'
import * as infra from '@foxcookieco/infrastructure'
import * as k8s from '@pulumi/kubernetes'
import * as config from './config'

export interface Process {
    name: string
    replicas: number
    image?: string
    command?: string[]
    ingress?: boolean
    monitoring?: boolean
    livenessProbe: 'default' | undefined | k8s.types.input.core.v1.Probe
    readinessProbe: 'default' | undefined | k8s.types.input.core.v1.Probe
    ports: 'default' | undefined
    resources: {
        [key: string]: {
            cpu: string
            memory: string
        }
    }
    autoscaling?: {
        maxReplicas: number,
        targetCPUUtilization: number
    }
}

export async function deployInfra(args: {
    environment: string
    namespace: string
    notify: string
}) {
    config.getProcesses(args.environment).map(process => {
        const traefikServiceName = pulumi.output(
            `${args.namespace}-${process.name}-8000_kubernetes`
        )

        if (process.monitoring) {
            new infra.monitor.SimpleMonitor(
                process.name,
                {
                    environment: args.environment,
                    namespace: args.namespace,
                    serviceName: traefikServiceName,
                    readinessProbeThreshold: 50,
                    notify: args.notify
                },
                {}
            )
        }
        if (process.name === 'web'  || process.name === 'worker') {
            new infra.monitor.UtilizationMonitor(
                process.name,
                {
                    environment: args.environment,
                    namespace: args.namespace,
                    podName: process.name,
                    notify: '@webhook-discord-monitoring-warning'
                }
            )
        }
    })
}

export async function deploy(args: {
    name: string
    env: string
    namespace: pulumi.Input<string>
    cluster: infra.kube.ClusterData
    dependsOn?: pulumi.Resource[]
}) {
    const secretEnv = (key: string): k8s.types.input.core.v1.EnvVar => {
        return {
            name: key,
            valueFrom: {
                secretKeyRef: {
                    name: `watchtower-${args.env}`,
                    key: key
                }
            }
        }
    }

    const secretEnvs = [
        secretEnv('DB_PASS'),
        secretEnv('DB_USER'),
        secretEnv('DFUSE_API_KEY'),
        secretEnv('DJANGO_SECRET_KEY'),
        secretEnv('ETHERSCAN_API_KEY'),
        secretEnv('INFURA_API_KEY'),
        secretEnv('ETH_GAS_STATION'),
        secretEnv('LAUNCH_DARKLY_SDK_KEY'),
        secretEnv('RABBIT_PASS'),
        secretEnv('RABBIT_USER')
    ]

    const db_migration = new infra.kube.Job(
        `${args.name}-db-migration`,
        {
            containers: [
                {
                    name: `${args.name}-db-migration`,
                    image: `${config.ecrEndpoint}/watchtower:${config.gitHash}`,
                    command: ['python', 'manage.py', 'migrate'],
                    resources: {
                        limits: {
                            cpu: '512m',
                            memory: '512Mi'
                        },
                        requests: {
                            cpu: '512m',
                            memory: '512Mi'
                        }
                    },
                    env: [{ name: 'ENVIRONMENT', value: args.env }, ...secretEnvs]
                }
            ],
            namespace: args.namespace
        },
        { provider: args.cluster.provider, dependsOn: args.dependsOn }
    )

    // create and deploy a "microservice" this will deploy a Kubernetes Deployment + service
    // A Deployment is like a ECS service it is used to control replicas of "pods"
    // A Pod
    return config
        .getProcesses(args.env)
        .map(process => {
            const microservice = new infra.kube.Microservice(
                process.name,
                {
                    containers: [
                        {
                            name: process.name,
                            image: process.image!,
                            livenessProbe: process.livenessProbe,
                            readinessProbe: process.readinessProbe,
                            ports: process.ports,
                            command: process.command,
                            resources: process.resources,
                            env: [{ name: 'ENVIRONMENT', value: args.env }, ...secretEnvs]
                        }
                    ],
                    replicas: process.replicas,
                    enableDatadogLogs: true,
                    datadogLogTags: [process.name],
                    namespace: args.namespace,
                    deploymentStrategy: {
                        rollingUpdate: { maxSurge: '50%', maxUnavailable: 0 }
                    }
                },
                { provider: args.cluster.provider, dependsOn: [db_migration] }
            )

            if (process.autoscaling) {
                new k8s.autoscaling.v1.HorizontalPodAutoscaler(
                    process.name,
                    {
                        metadata: {
                            namespace: args.namespace
                        },
                        spec: {
                            minReplicas: process.replicas,
                            maxReplicas: process.autoscaling.maxReplicas,
                            scaleTargetRef: {
                                name: microservice.metadata.name,
                                kind: microservice.kind,
                                apiVersion: microservice.apiVersion
                            },
                            targetCPUUtilizationPercentage: process.autoscaling.targetCPUUtilization
                        }
                    },
                    { provider: args.cluster.provider }
                )
            }

            if (process.ingress) {
                // Make accessible from outside the cluster
                const ingress = new infra.kube.SimpleIngress(
                    process.name,
                    {
                        microservice: microservice,
                        subDomain: pulumi.interpolate`${args.namespace}-${process.name}`,
                        rootDomain: args.cluster.domain // <subDomain> + <rootDomain> = watchtower-web.megacluster.stage.redacted.example.com
                    },
                    { provider: args.cluster.provider }
                )

                return ingress.url
            }
            return undefined
        })
        .filter(Boolean)
}

export function deployEphemeralDatabases(args: {
    namespace: pulumi.Output<string>
    cluster: infra.kube.ClusterData
}) {
    const redisPVC = new k8s.core.v1.PersistentVolumeClaim(
        'redis',
        {
            metadata: {
                name: 'redis',
                namespace: args.namespace
            },
            spec: {
                accessModes: ['ReadWriteOnce'],
                storageClassName: 'gp2',
                resources: {
                    requests: {
                        storage: '8Gi'
                    }
                }
            }
        },
        { provider: args.cluster.provider }
    )

    // using `redis-cache` instead of `redis` to avoid creating a `REDIS_PORT`env var in the namespace
    const redis = new infra.kube.Microservice(
        'redis',
        {
            replicas: 1,
            namespace: args.namespace,
            containers: [
                {
                    image: 'redis',
                    name: 'redis',
                    command: ['redis-server', '--appendonly', 'yes'],
                    ports: [{ containerPort: 6379 }],
                    resources: {
                        limits: {
                            cpu: '100m',
                            memory: '250Mi'
                        }
                    },
                    volumeMounts: [{ name: 'data', mountPath: '/data' }]
                }
            ],
            volumes: [{ name: 'data', persistentVolumeClaim: { claimName: 'redis' } }]
        },
        { provider: args.cluster.provider }
    )

    // We can inject sql on startup if we want with this
    //    const postgresInitScript = new k8s.core.v1.ConfigMap(
    //        'postgres-init',
    //        {
    //            metadata: {
    //                name: 'postgres-init',
    //                namespace: args.namespace
    //            },
    //            data: {
    //                'init.sh': `
    //#!/bin/bash
    //set -e
    //psql -v ON_ERROR_STOP=1 --username postgres --dbname axiom <<-EOSQL
    //    CREATE DATABASE axiomfox;
    //    GRANT ALL PRIVILEGES ON DATABASE axiomfox TO postgres;
    //EOSQL`
    //            }
    //        },
    //        { provider: args.cluster.provider }
    //    )

    const postgresPVC = new k8s.core.v1.PersistentVolumeClaim(
        'postgres',
        {
            metadata: {
                name: 'postgres',
                namespace: args.namespace
            },
            spec: {
                accessModes: ['ReadWriteOnce'],
                storageClassName: 'gp2',
                resources: {
                    requests: {
                        storage: '8Gi'
                    }
                }
            }
        },
        { provider: args.cluster.provider }
    )

    const postgres = new infra.kube.Microservice(
        'postgres',
        {
            replicas: 1,
            namespace: args.namespace,
            // We only need this if we want to run the injected sql
            //volumes: [
            //    {
            //        name: 'init',
            //        configMap: {
            //            name: postgresInitScript.metadata.name
            //        }
            //    }
            //],
            //volumeMounts: [{ name: 'init', mountPath: '/docker-entrypoint-initdb.d/' }],
            containers: [
                {
                    image: 'postgres',
                    name: 'postgres',
                    ports: [{ containerPort: 5432 }],
                    env: [
                        {
                            name: 'POSTGRES_DB',
                            value: 'watchtower'
                        },
                        {
                            name: 'POSTGRES_PASSWORD',
                            value: 'password'
                        },
                        {
                            name: 'PGDATA',
                            value: '/var/lib/postgresql/data/pgdata'
                        }
                    ],
                    resources: {
                        limits: {
                            cpu: '100m',
                            memory: '250Mi'
                        }
                    },
                    volumeMounts: [{ name: 'data', mountPath: '/var/lib/postgresql/data' }]
                }
            ],
            volumes: [{ name: 'data', persistentVolumeClaim: { claimName: 'postgres' } }]
        },
        { provider: args.cluster.provider }
    )

    const [rabbitSTS, rabbitIngressURL] = createRabbitSTS(args.namespace, args.cluster.provider)

    return { redis, postgres, rabbitSTS, rabbitIngressURL }
}

function createRabbitSTS(
    namespace: string | pulumi.Output<string>,
    provider: pulumi.ProviderResource
) {
    const container: k8s.types.input.core.v1.Container = {
        image: 'rabbitmq:3.8.0-management',
        name: 'rabbitmq',
        ports: [
            { name: 'api', containerPort: 5672 },
            { name: 'dashboard', containerPort: 15672 }
        ],
        env: [
            {
                name: 'RABBITMQ_DEFAULT_USER',
                value: 'guest'
            },
            {
                name: 'RABBITMQ_DEFAULT_PASS',
                value: 'guest'
            },
            {
                name: 'RABBITMQ_DEFAULT_VHOST',
                value: '/'
            },
            {
                name: 'RABBITMQ_VM_MEMORY_HIGH_WATERMARK',
                value: '1.0'
            }
        ],
        resources: {
            limits: {
                cpu: '150m',
                memory: '350Mi'
            }
        },
        volumeMounts: [{ name: 'data', mountPath: '/var/lib/rabbitmq' }]
    }

    const podSpec: k8s.types.input.core.v1.PodTemplateSpec = {
        metadata: {
            namespace: namespace,
            labels: { app: 'rabbitmq' }
        },
        spec: {
            containers: [container]
        }
    }

    const sts = new k8s.apps.v1.StatefulSet(
        'rabbitmq-sts',
        {
            metadata: {
                name: 'rabbitmq',
                namespace: namespace
            },
            spec: {
                selector: { matchLabels: { app: 'rabbitmq' } },
                serviceName: 'rabbitmq',
                replicas: 1,
                template: podSpec,
                volumeClaimTemplates: [
                    {
                        metadata: {
                            name: 'data'
                        },
                        spec: {
                            accessModes: ['ReadWriteOnce'],
                            storageClassName: 'gp2',
                            resources: {
                                requests: {
                                    storage: '1Gi'
                                }
                            }
                        }
                    }
                ]
            }
        },
        { provider }
    )

    const svc = new k8s.core.v1.Service(
        'rabbitmq-svc',
        {
            metadata: {
                name: 'rabbitmq',
                namespace: namespace
            },
            spec: {
                ports: [
                    { port: 5672, protocol: 'TCP', name: 'rabbitmq' },
                    {
                        port: 15672,
                        protocol: 'TCP',
                        name: 'rabbitmqadmin'
                    }
                ],
                selector: {
                    app: 'rabbitmq'
                },
                type: 'ClusterIP'
            }
        },
        { provider }
    )

    const url = pulumi.interpolate`${namespace}-rabbitmq.megacluster.stage.redacted.example.com`

    const ingress = new k8s.networking.v1beta1.Ingress(
        `rabbitmq-ingress`,
        {
            metadata: {
                namespace: namespace
            },
            spec: {
                rules: [
                    {
                        host: url,
                        http: {
                            paths: [
                                {
                                    backend: {
                                        serviceName: svc.metadata.name,
                                        servicePort: svc.spec.ports[1].port
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        },
        { provider }
    )

    return [sts, url]
}
