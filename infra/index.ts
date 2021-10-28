import * as infra from '@foxcookieco/infrastructure'
import * as pulumi from '@pulumi/pulumi'
import * as k8s from '@pulumi/kubernetes'

import { buildImage } from './build'
import { deploy, deployEphemeralDatabases, deployInfra } from './deploy'
import * as config from './config'

export const outputs = (async () => {
    const service_name = 'watchtower'
    const env = pulumi.getStack().includes('ephemeral') ? 'ephemeral' : pulumi.getStack()

    const build = async () => {
        // we don't want healthMonitor for ephemeral
        if (env !== 'ephemeral') {
            const baseImageECREndpoint = await buildImage(service_name, '..', '../Dockerfile')
            const healthMonitorECREndpoint = await buildImage(
                `${service_name}-monitor`,
                '..',
                '../health-monitor/Dockerfile'
            )
            return [baseImageECREndpoint, healthMonitorECREndpoint]
        }

        return await buildImage(service_name, '..', '../Dockerfile')
    }

    switch (env) {
        case 'infra':
            deployInfra({
                environment: 'prod',
                namespace: 'watchtower',
                notify: '@webhook-discord-monitoring-critical'
            })
            return

        case 'build':
            return await build()

        case 'stage':
        case 'prod': {
            const cluster = infra.kube.getClusterData('megacluster', env as 'stage' | 'prod')

            return deploy({
                name: service_name,
                namespace: 'watchtower',
                env,
                cluster
            })
        }

        case 'ephemeral': {
            const cluster = infra.kube.getClusterData('megacluster', 'stage')
            const namespace = new infra.kube.EphemeralNamespace(
                `watchtower-${config.sanatizedGitBranch}`, // make namespace off branch name, and replace invalid characters with '-'
                { provider: cluster.provider }
            ).metadata.name

            const databases = deployEphemeralDatabases({ namespace, cluster })

            await build()

            const urls = await deploy({
                name: service_name,
                env,
                namespace,
                cluster,
                dependsOn: [
                    databases.postgres,
                    databases.rabbitSTS as pulumi.Resource,
                    databases.redis
                ]
            })

            return [...urls, databases.rabbitIngressURL]
        }
        default:
            console.error(
                `Invalid stack name '${env}'. Only 'build', 'stage', 'prod', or '*ephemeral*' is allowed.`
            )
            process.exit(1)
    }
})()
