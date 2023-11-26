# Ignition Server

Small api aiming to serve ignition manifests dynamically on-the-fly.

## The need

To install [CoreOS](https://fedoraproject.org/coreos/)/[Flatcar](https://www.flatcar.org/) you need to expose the static ignition file via an HTTP server and the use it remotely in your installation live session or you have to copy your static ignition file locally in your installation live session.

The pain increase with th number of servers to deploy.

## The solution

Instead of serve the ignition configs for each deployment you need, you can generate the ignition configs on-the-fly from [butane templates](https://coreos.github.io/butane/specs/) you can customize as you want.

### How to use

```bash
docker pull ghcr.io/soubinan/ignition-server:latest

docker run --rm -v $PWD/templates:/app/templates:Z -p 8000:8000 ghcr.io/soubinan/ignition-server:latest
```

### Demo

<https://ignition-server.soubilabs.xyz>
