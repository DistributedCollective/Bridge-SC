# Gitlab CI

## Configuration - Merge and push permissions

You need to configure the following settings when creating the repository:

- Prevent merge pushes on develop and master
  - To avoid people skipping pipeline's executions.
  - Go to the project Gitlab Site, then `Settings (⚙) > Repository > Protected Branches (click on Expand)"` and configure:
    - `master`: `allowed to merge (maintainers)`, `allowed to push (maintainers)`
    - `develop`: `allowed to merge (developers + maintainers)`, `allowed to push (maintainers)`
- Ask for the pipeline to succeed before merging.
  - In order to not to break any important branch.
  - Go to the project Gitlab Site, then `Settings (⚙) > General > Merge Requests (click on Expand) > Merge checks: "Pipelines must succeed"`

## Configuring the project

In order make GitlabCI to recognize a project, you need to declare a `.gitlab-ci.yml` file in the root folder. The configuration is quite similar to the ones used by CircleCI, Travis, etc. Full spec can be found [here](https://docs.gitlab.com/ee/ci/yaml/) although there are several templates that can be foun [here](../examples/).

- Do not forget to rename gitlab yaml files to `.gitlab-ci.yml` otherwise it won't be picked by the CI server.
- Templates provided here should be enough for 80% of the time you need to configure a project. **Reusing them is encouraged as you will share the same configuration as other projects.**
- Each project will use, in general, three different `.gitlab-ci.yml` files:
  1. The one that builds and package the frontend.
  2. The one that builds and package the backend.
  3. The one that handles the deploys.

## Considerations

- Deploys must be declared as manual jobs.
- Atix Docker Hub Credentials are stored as protected variables in Atix's Gitlab organization so you can use them to login and push the images.
- Before deploying you need to update, commit and push the Docker Compose file specifying the image versions to be deployed.
- **Don't forget to bump backend and api versions before building a new docker image or them will be replaced (that needs to be fixed).**
- Try to use already defined images to run your jobs. If you can't find the one that you are looking for, you can create your own and push it to either Docker or Atix registry (i.e. the one we built with Docker with Docker-Compose installed).
- You can access [Atix registry](https://docker.atixlabs.com) using your google credentials.

## Running the Jobs Locally

Steps can be found in this [blogpost](https://www.akitaonrails.com/2018/04/28/smalltips-running-gitlab-ci-runner-locally).

Keep in mind that:

- It might speed up your work as you don't need to push your `.gitlab-ci.yml` everything and wait for GitlabCI to pick the work
- It _seems_ you can't make cache work if you run it locally.
- It will checkout a remote commit so local code changes won't work (apparently this is made due to security reasons as your local job might deploy something by mistake. [Ref](https://gitlab.com/gitlab-org/gitlab-runner/issues/1359)).
