# Remote Environment Setup

Remote environment setup is performed using an [Ansible playbook](https://docs.ansible.com/ansible/latest/user_guide/playbooks.html). [Ansible](https://www.ansible.com) is an easy to setup (as no remote hosting is required) IT infrastructure automation tool. A playbook is a way to language that can be used to describe an automation process.

This playbook relies on [Ansible Galaxy](https://galaxy.ansible.com/), a repository for common Ansible recipes (named roles).

## Prerequisites

To setup a remote environment, what you need to do is:

1. Launch the VPS instance (linux - Ubuntu or Debian stable version) and configure the `root`'s `authorized_keys` file in order to contain your public ssh key (Linode and AWS allow you to do this before launching the server).
2. Once the server is launched, configure the following domains for each environment (staging and uat):

| Name                                  | Value                             | Type         |
| ------------------------------------- | --------------------------------- | ------------ |
| $project-$environment.atixlabs.com    | x.x.x.x                           | A Record     |
| \*.$environment.$project.atixlabs.com | \$project-environent.atixlabs.com | CNAME Record |

So, for example, the routing table for project `MyProject` should be:

| Name                              | Value                          | Type         |
| --------------------------------- | ------------------------------ | ------------ |
| myproject-staging.atixlabs.com    | 173.10.33.86                   | A Record     |
| \*.staging.myproject.atixlabs.com | myproject-staging.atixlabs.com | CNAME Record |
| myproject-uat.atixlabs.com        | 173.23.54.61                   | A Record     |
| \*.uat.myproject.atixlabs.com     | myproject-staging.atixlabs.com | CNAME Record |

_Note: Production is probably a separate case as it's likely the domain won't be `atixlabs.com`. That being said, we should try to keep `api.domain.com` as the API endpoint and `domain.com` for the frontend just to be consisten with our naming. This obviously should be agreed by the Product Owner and je must make the final decision._

3. Install Ansible. See [this guide](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html).
4. Install playbook dependencies, to do so:

```
cd ansible && ./install-roles.sh
```

5. Update `./$ENVIRONMENT/` configs in order to set values for each environment.

## Running the setup

Running the `setup-environment.sh` script will execute the Ansible Playbook that will ssh into the server and:

- Create a user named `app`.
- Set the `authorized_keys` to the configured keys allowing them to login using ssh.
- Install `docker` and `docker-compose`
- Configure and `IPTABLES` firewall using `ufw` in order to block everything except SSH, HTTP and HTTPS traffic.

For example, to setup staging, you will need to:

```
cd ansible && ./setup-environment.sh "staging"
```

## FAQ

**Q:** Can I install more things than the ones specified here?

**A:** Even if you have access to the server and this scripts it's **strongly encouraged not to change this deploy process. We are aiming to have, as long as we can, all the environments configured the same way**. Rather than that create a pull request to update upstream Atix-Ops repository if you consider it might be a good addition.

---

**Q:** Can I add another ssh key after creating the environment?

**A:** Yes, just add the key and [execute the script](###Running-the-setup) again.

---

**Q:** If database port is not being exposed when setting up the firewall, how can I access the DB?

**A:** Just add your key to grant you access over ssh and then redirect the port to your machine. For example, if you want to get access to a postgres deployed DB you can do:

```
ssh app@my-server.com -L5432:localhost:5432
```
