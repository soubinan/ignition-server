import subprocess
import tempfile
import os
import sys
import logging

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from dotenv import load_dotenv


load_dotenv('./templates/.env')

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)


def _build_ignition(butane_filepath, params):
    with open(f'{butane_filepath}.yaml', 'r') as f:
        bu = f.read()

        for k,v in params.items():
            bu = bu.replace(f'$${k}$$', v)

        with tempfile.NamedTemporaryFile() as t:
            t.write(bytes(bu, 'utf-8'))
            t.read()
            cmd = f'./butane --pretty --strict {t.name}'.split()
            run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        ign = run.stdout.decode("utf-8")

    if run.returncode == 0:
        return None, ign
    else:
        return f'ignition build error: {run.stdout.decode("utf-8")}', None


def _serve_ignition(parsed_path):
    params = {}
    ign = None
    err = None

    try:
        params = {q.split('=')[0]: q.split('=')[1] for q in (parsed_path.query).split('&') if (len(q)>0 and '=' in q)}

        if 'template_id' in params:
            template_id = os.getenv(params['template_id'])
            params = {q.split('=')[0]: q.split('=')[1] for q in template_id.split('&') if (len(q)>0 and '=' in q)}

        config_path = f"templates/{params.get('type', 'unknown_type')}/{params.get('group', 'unknown_group')}"

        err, ign = _build_ignition(config_path, params)

    except Exception as e:
            advice = '\n'.join([
                'Advice:',
                'Your request should follow the pattern below',
                'Expected URI: host/<required part>?<optional part>',
                'Required part can be:',
                '    /ignition?type=<cloud|metal>&group=<ignition filename>[?<optional part>]',
                ' or',
                '    /ignition?template_id=<template_id>',
                'Optional part: key1=value1&key2=value2...',
                '',
            ])

            err = f'{e}\n\n{advice}'

    finally:
        logging.debug(f'parameters: {params}')
        return err, ign


def _serve_home(**kwargs):
    return '\n'.join([
        'CLIENT VALUES:',
        f"client_address={kwargs.get('client_address')} {kwargs.get('address_string')()}",
        f"command={kwargs.get('command')}",
        f"path={kwargs.get('path')}",
        f"real path={kwargs.get('parsed_path').path}",
        f"query={kwargs.get('parsed_path').query}",
        f"request_version={kwargs.get('request_version')}",
        '',
        'SERVER VALUES:',
        f"server_version={kwargs.get('server_version')}",
        f"sys_version={kwargs.get('sys_version')}",
        f"protocol_version={kwargs.get('protocol_version')}",
        '',
        ])


class GetHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        err = None

        if parsed_path.path == '/':
            message = _serve_home(
                client_address=self.client_address,
                address_string=self.address_string,
                command=self.command,
                path=self.path,
                parsed_path=parsed_path,
                request_version=self.request_version,
                server_version=self.server_version,
                sys_version=self.sys_version,
                protocol_version=self.protocol_version,
            )
        elif parsed_path.path == '/ignition':
            err, message = _serve_ignition(parsed_path)
        else:
            message = None

        if message and isinstance(message, str):
            self.send_response(200)
        elif err:
            message = f'400: Bad request:\n{err}'
            self.send_response(400)
        else:
            message = '404: Not Found'
            self.send_response(404)
        self.end_headers()
        self.wfile.write(message.encode('utf-8'))
        return


if __name__ == '__main__':
    listening_src = '0.0.0.0'
    listening_port = 8899
    server = HTTPServer((listening_src, listening_port), GetHandler)
    logging.info(f'Serving ignition at http://{listening_src}:{listening_port}')
    logging.warning(f'!!! Do not be used publicly !!!')
    server.serve_forever()