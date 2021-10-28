import * as infra from '@foxcookieco/infrastructure'
import * as pulumi from '@pulumi/pulumi'
import * as k8s from '@pulumi/kubernetes'
import { Process } from './deploy'

export const ecrEndpoint = `redacted.example.com`
export const gitHash = infra.git.getInfo().hash.short
export const sanatizedGitBranch = infra.git
    .getInfo()
    .branch.toLocaleLowerCase()
    .replace(/[^a-zA-Z0-9]/g, '-')

export function getProcesses(env: string): Process[] {
    1
    const webReadinessProbe: k8s.types.input.core.v1.Probe = {
        exec: {
            command: ['./isWebReady.sh']
        },
        initialDelaySeconds: 30,
        periodSeconds: 10,
        failureThreshold: 2,
        successThreshold: env === 'prod' ? 5 : 1,
        timeoutSeconds: 3
    }

    const monitor: Process = {
        name: 'watchtower-monitor',
        replicas: 1,
        image: `${ecrEndpoint}/watchtower-monitor:${gitHash}`,
        command: ['monitor'],
        livenessProbe: undefined,
        readinessProbe: undefined,
        ports: 'default',
        resources: {
            limits: {
                cpu: '64m',
                memory: '128Mi'
            },
            requests: {
                cpu: '64m',
                memory: '128Mi'
            }
        }
    }

    const nonEphemeralProcess = (() => {})()

    const processes: Process[] = [
        {
            name: 'web',
            replicas: env === 'prod' ? 18 : 3,
            image: `${ecrEndpoint}/watchtower:${gitHash}`,
            command: ['gunicorn', '-c', `config/gunicorn.${env}.py`, 'watchtower.wsgi:application'],
            ingress: true,
            monitoring: env === 'prod' ? true : false,
            livenessProbe: {
                tcpSocket: {
                    port: 8000
                }
            },
            readinessProbe: env !== 'ephemeral' ? webReadinessProbe : undefined,
            ports: 'default',
            resources: {
                limits: {
                    cpu: '2048m',
                    memory: '2Gi'
                },
                requests: {
                    cpu: '2048m',
                    memory: '2Gi'
                }
            },
            autoscaling: {
                maxReplicas: 40,
                targetCPUUtilization: 15
            }
        },
        // create second web instance for bi/finance
        // as gunicorn requires longer running timeouts for the larger queries
        // We don't this process in ephemeral environments
        ...((): Process[] => {
            if (env !== 'ephemeral')
                return [
                    {
                        name: 'web-finance',
                        replicas: env === 'prod' ? 2 : 2,
                        image: `${ecrEndpoint}/watchtower:${gitHash}`,
                        command: [
                            'gunicorn',
                            '-c',
                            `config/gunicorn.${env}.finance.py`,
                            'watchtower.wsgi:application'
                        ],
                        ingress: true,
                        livenessProbe: {
                            tcpSocket: {
                                port: 8000
                            }
                        },
                        readinessProbe: {
                            tcpSocket: {
                                port: 8000
                            }
                        },
                        ports: 'default',
                        resources: {
                            limits: {
                                cpu: '1024m',
                                memory: '512Mi'
                            },
                            requests: {
                                cpu: '1024m',
                                memory: '512Mi'
                            }
                        }
                    }
                ]

            return []
        })(),
        {
            name: 'scheduler',
            replicas: 1,
            image: `${ecrEndpoint}/watchtower:${gitHash}`,
            command: [
                'celery',
                '-A',
                'watchtower',
                'beat',
                '-l',
                'info',
                '--scheduler',
                'django_celery_beat.schedulers:DatabaseScheduler'
            ],
            livenessProbe: undefined,
            readinessProbe: undefined,
            ports: 'default',
            resources: {
                limits: {
                    cpu: '128m',
                    memory: '256Mi'
                },
                requests: {
                    cpu: '128m',
                    memory: '256Mi'
                }
            }
        },
        {
            name: 'worker',
            replicas: (() => {
                switch (env) {
                    case 'prod':
                        return 20
                    case 'stage':
                        return 20
                    case 'ephemeral':
                        return 3
                    default:
                        return 3
                }
            })(),
            image: `${ecrEndpoint}/watchtower:${gitHash}`,
            command: ['celery', '-A', 'watchtower', 'worker', '-l', 'info', '-O', 'fair'],
            livenessProbe: undefined,
            readinessProbe: undefined,
            ports: 'default',
            resources: {
                limits: {
                    cpu: '256m',
                    memory: '2048Mi'
                },
                requests: {
                    cpu: '256m',
                    memory: '2048Mi'
                }
            }
        },
        //{
        //    name: 'flower',
        //    replicas: 1,
        //    image: `${ecrEndpoint}/watchtower:${gitHash}`,
        //    command:
        //        'celery -A watchtower flower --port=8000 --persistent=True --db=flower --broker=$REDIS_URL --broker_api=$REDIS_URL',
        //    livenessProbe: undefined,
        //    readinessProbe: undefined,
        //    ingress: true,
        //    ports: 'default',
        //    resources: {
        //        limits: {
        //            cpu: '128m',
        //            memory: '128Mi'
        //        },
        //        requests: {
        //            cpu: '128m',
        //            memory: '128Mi'
        //        }
        //    }
        //},
        {
            name: 'bnb-websocket-consumer',
            replicas: 1,
            image: `${ecrEndpoint}/watchtower:${gitHash}`,
            command: ['python', 'manage.py', 'bnb_queue_blocks'],
            livenessProbe: undefined,
            readinessProbe: undefined,
            ports: 'default',
            resources: {
                limits: {
                    cpu: '64m',
                    memory: '256Mi'
                },
                requests: {
                    cpu: '64m',
                    memory: '256Mi'
                }
            }
        },

        {
            name: 'unchained-event-ingester',
            replicas: 1,
            image: `${ecrEndpoint}/watchtower:${gitHash}`,
            command: ['python', 'manage.py', 'ingest_unchained_events'],
            livenessProbe: undefined,
            readinessProbe: undefined,
            ports: 'default',
            resources: {
                limits: {
                    cpu: '64m',
                    memory: '256Mi'
                },
                requests: {
                    cpu: '64m',
                    memory: '256Mi'
                }
            }
        },

        // no monitor for ephemerals
        ...(env !== 'ephemeral' ? [monitor] : [])
    ]
    return processes
}
