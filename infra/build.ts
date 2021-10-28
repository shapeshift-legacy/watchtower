import * as infra from '@foxcookieco/infrastructure'
import * as pulumi from '@pulumi/pulumi'
import { ecrEndpoint, gitHash, sanatizedGitBranch } from './config'

export async function buildImage(
    name: string,
    context: string,
    dockerfile: string
): Promise<pulumi.Output<string>> {
    const repo = `${ecrEndpoint}/${name}`
    const latestBranchTag = `${sanatizedGitBranch}-latest`

    const baseImage = await infra.docker.buildAndPushImage(
        name,
        [gitHash, latestBranchTag],
        {
            context: context,
            dockerfile: dockerfile,
            env: {
                DOCKER_BUILDKIT: '1'
            },
            args: {
                NPM_TOKEN: `${process.env.NPM_TOKEN}`,
                BUILDKIT_INLINE_CACHE: '1'
            }
        },
        [`${repo}:${latestBranchTag}`, `${repo}:latest`, `${repo}:master-latest`],
        false,
        ''
    )

    return pulumi.output(baseImage.imageName)
}
