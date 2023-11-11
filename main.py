import os
import sys
import subprocess
import json
import logging

from pathlib import Path
from tempfile import mkstemp
from yaml import safe_load
from fastapi import FastAPI, Response, status
from jinja2 import Environment, PackageLoader, select_autoescape, meta
from jinja2.exceptions import TemplateNotFound
from pydantic import BaseModel, create_model, ValidationError


env = Environment(
    loader=PackageLoader("main"),
    autoescape=select_autoescape()
)

logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('%(levelname)s:    %(message)s'))
logger.addHandler(handler)


class Params(BaseModel):
    name: str

app = FastAPI()

@app.get('/')
def read_root():
    return {'message': 'ok'}

@app.post('/generate', status_code=200)
def read_item(params: dict, response: Response):
    primaries = {'name'}
    vars = {}

    try:
        template_name = params['name']
        template_path = f'./{template_name}.yaml'
        template_source = env.loader.get_source(env, template_path)
        parsed_content = env.parse(template_source)
        vars = meta.find_undeclared_variables(parsed_content)
        fields = dict.fromkeys(vars, (str | int, ...))
        DynamicParamsModel = create_model('DynamicParamsModel', **fields)
        values = DynamicParamsModel(**params)

        template = env.get_template(template_path)
        result = template.render(values)
        td, n = mkstemp(text=True)

        with open(td, 'w') as t:
            t.write(result)
            cmd = f'./butane -d templates --strict {n}'.split()
        run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = run.stdout.decode("utf-8")
        Path(n).unlink(missing_ok=True)
        return json.loads(out)
    except KeyError as e:
        logger.error(e)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            'details': 'Bad request',
            'error': f'Missing One or Many Primary Parameters. Expected parameters: {primaries}',
            }
    except ValidationError as e:
        logger.error(e)
        response.status_code = status.HTTP_400_BAD_REQUEST
        additional = {v for v in vars if v not in {"name"}}
        return {
            'details': 'Bad request',
            'error': f'Missing One or Many Additional Parameters. Expected parameters: {additional}',
            }
    except TemplateNotFound as e:
        logger.exception(e)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            'details': 'Bad Request',
            'error': 'Template name not known',
            }
    except Exception as e:
        logger.exception(e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'details': 'Internal Server Error',
            }

@app.get('/generate/{template_id}', status_code=200)
def read_item(template_id: str, response: Response):
    try:
        with open('./templates/params.yaml') as p:
            params = safe_load(p.read())

        param = params[template_id]
        template = env.get_template(param['template'])
        result = template.render(param)
        td, n = mkstemp(text=True)

        with open(td, 'w') as t:
            t.write(result)
            cmd = f'./butane -d templates --strict {n}'.split()
        run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        out = run.stdout.decode("utf-8")
        Path(n).unlink(missing_ok=True)
        return json.loads(out)
    except KeyError as e:
        logger.error(e)
        response.status_code = status.HTTP_404_NOT_FOUND
        return {'details': 'Not Found'}
    except TemplateNotFound as e:
        logger.exception(e)
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            'details': 'Bad Request',
            'error': 'Template name not known',
            }
    except Exception as e:
        logger.exception(e)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {
            'details': 'Internal Server Error',
            }