import os
import sys
import subprocess
import json
import logging
import yaml

from typing import Any
from pathlib import Path
from tempfile import mkstemp
from fastapi import FastAPI, UploadFile, status
from fastapi.responses import JSONResponse, FileResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from jinja2 import Environment, PackageLoader, select_autoescape, meta
from jinja2.exceptions import TemplateNotFound
from pydantic import BaseModel, Field, ConfigDict, create_model, ValidationError


env = Environment(
    loader=PackageLoader("main"),
    autoescape=select_autoescape()
)

logger = logging.getLogger()
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter('%(levelname)s:\t%(message)s'))
logger.addHandler(handler)

TEMPLATES_DIRPATH = '/app/templates'
BLUEPRINT_FILEPATH = '/app/templates/__blueprints.yaml'

class Param(BaseModel):
    name: str = Field(title='The name of the template to be used to generate the ignition manifest', max_length=100)
    model_config: str|int|dict = ConfigDict(extra='allow')

class Blueprint(BaseModel):
    name: str = Field(title='The name of the blueprint to be used to generate the ignition manifest', max_length=100)
    template: str = Field(title='The path of the template to be used with the blueprint', max_length=100)
    model_config: str|int|dict = ConfigDict(extra='allow')

def _ignition_generation(butane_config_filename):
        cmd = f'butane --files-dir {TEMPLATES_DIRPATH} --strict --check {butane_config_filename}'.split()
        run = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        msg = {
            'message': f'Submitted butane config not valid',
            'error': f'{run.stdout.decode("utf-8")}'.split('\n'),
        }

        if run.stdout:
            raise SyntaxError(msg)

        from random import choice as r_choice
        from string import ascii_letters

        ignition_config_filename = f'/tmp/{''.join(r_choice(ascii_letters) for _ in range(10))}'

        cmd = f'butane --files-dir {TEMPLATES_DIRPATH} --strict --pretty --raw {butane_config_filename} --output {ignition_config_filename}'.split()
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        msg = run.stdout.decode("utf-8")

        if run.stdout:
            raise Warning(msg)

        with open(ignition_config_filename) as i:
            res = i.read()

        return res

description = """
## The need

To install CoreOS/Flatcar you need to expose the ignition file on an HTTP server and the use it remotely from your installation live session or you have to have a copy of your ignition file locally in your installation live session.

The pain increase with th number of servers to deploy.

## The solution

Instead of serve the ignition configs for each deployment you need, you can generate the ignition configs on-the-fly from butane templates you can customize as you want.
"""

app = FastAPI(
    title = 'Ignition Server',
    summary = 'Get, Add and Update Ignition configurations via a simple and flexible API',
    description = description,
    version = os.getenv('API_VERSION'),
    contact={
        "name": "Ignition Server",
        "url": "https://github.com/soubinan/ignition-server",
    },
)

@app.get('/', status_code=200, tags=['Home'])
def home() -> JSONResponse:

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={'details': {
            'info': 'Go to /redocs for more info',
            'test': 'Go to /docs to test',
            },}
    )

@app.post('/configs', status_code=202, tags=['Configurations'], description='Generate an Ignition config from parameters query')
def generate_config(param: Param,) -> JSONResponse:
    try:
        template_name = param.name
        template_path = f'./{template_name}.yaml'
        template_source = env.loader.get_source(env, template_path)
        parsed_content = env.parse(template_source)
        fields = meta.find_undeclared_variables(parsed_content)
        DynamicParamsModel = create_model('DynamicParamsModel', **{field: (Any, ...) for field in fields if field != 'name'}, __base__=Param)
        values = DynamicParamsModel(**param.model_dump())
        template = env.get_template(template_path)
        result = template.render(values)
        td, n = mkstemp(text=True)

        with open(td, 'w') as t:
            t.write(result)

        out = _ignition_generation(n)
        Path(n).unlink(missing_ok=True)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=json.loads(out)
        )
    except SyntaxError as e:
        logger.info(e)

        return JSONResponse(
            status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={'details': json.loads(e),}
        )
    except ValidationError as e:
        logger.info(e)

        return JSONResponse(
            status_code = status.HTTP_510_NOT_EXTENDED,
            content={'details': json.loads(e.json()),}
        )
    except TemplateNotFound as e:
        logger.info(e)

        return JSONResponse(
            status_code = status.HTTP_510_NOT_EXTENDED,
            content={'details': f'Template {template_name} not found',}
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.get('/configs/{blueprint_id}', status_code=200, tags=['Configurations'], description='Generate an Ignition config from a predefined blueprint')
def get_config(blueprint_id: str,) -> JSONResponse:
    blueprint = ''

    try:
        with open(BLUEPRINT_FILEPATH) as b:
            blueprints = yaml.safe_load(b.read())
            blueprint = blueprints[blueprint_id]

        template = env.get_template(blueprint['template'])
        result = template.render(blueprint)
        td, n = mkstemp(text=True)

        with open(td, 'w') as t:
            t.write(result)

        out = _ignition_generation(n)
        Path(n).unlink(missing_ok=True)

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=json.loads(out)
        )
    except SyntaxError as e:
        logger.info(e)

        return JSONResponse(
            status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            content={'details': e.msg,}
        )
    except KeyError as e:
        status_code = status.HTTP_404_NOT_FOUND

        if blueprint:
            logger.info(out)

            return JSONResponse(
                status_code = status_code,
                content={'details': 'Invalid Blueprint: Missing template path',}
            )
        else:
            logger.info(e)
            return JSONResponse(
                status_code = status_code,
                content={'details': f'Blueprint {blueprint_id} not found',}
            )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Mandatory Blueprints file {BLUEPRINT_FILEPATH} not found',}
            )
    except TemplateNotFound as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_510_NOT_EXTENDED,
                content={'details': f'Template {blueprint['template']} not found',}
            )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.get('/blueprints/{blueprint_id}', status_code=200, tags=['Blueprints'], description='Get one specific blueprint')
def get_blueprint(blueprint_id: str,) -> JSONResponse:
    try:
        with open(BLUEPRINT_FILEPATH) as b:
            blueprints = yaml.safe_load(b.read())
            blueprint = blueprints[blueprint_id]

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=blueprint
        )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Mandatory Blueprints file {BLUEPRINT_FILEPATH} not found',}
            )
    except KeyError as e:
        status_code = status.HTTP_404_NOT_FOUND

        logger.info(e)
        return JSONResponse(
            status_code = status_code,
            content={'details': f'Blueprint {blueprint_id} not found',}
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.get('/blueprints', status_code=200, tags=['Blueprints'], description='Get available blueprints list')
def get_blueprints() -> JSONResponse:
    try:
        with open(BLUEPRINT_FILEPATH) as b:
            blueprints = yaml.safe_load(b.read())

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=blueprints
        )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Mandatory Blueprints file {BLUEPRINT_FILEPATH} not found',}
            )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.post('/blueprints', status_code=201, tags=['Blueprints'], description='Add a new blueprint')
def add_blueprint(blueprint: Blueprint,) -> JSONResponse:
    try:
        with open(BLUEPRINT_FILEPATH) as b:
            blueprints = yaml.safe_load(b.read())

        if blueprint.name in blueprints:
            raise ValueError(f'Blueprint ID {blueprint.name} already exists')

        blueprints[blueprint.name] = {k:v for k,v in blueprint.model_dump().items() if k != 'name'}

        with open(BLUEPRINT_FILEPATH, 'w') as b:
            yaml.dump(blueprints, b)

        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content=blueprints
        )
    except ValueError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_409_CONFLICT,
                content={'details': f'Blueprint ID {blueprint.name} already exists',}
            )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Mandatory Blueprints file {BLUEPRINT_FILEPATH} not found',}
            )
    except KeyError as e:
        status_code = status.HTTP_404_NOT_FOUND

        logger.info(e)
        return JSONResponse(
            status_code = status_code,
            content={'details': f'Blueprint {blueprint.name} not found',}
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.put('/blueprints/{blueprint_id}', status_code=202, tags=['Blueprints'], description='Update an existing blueprint')
def update_blueprint(blueprint_id: str, blueprint: Blueprint,) -> JSONResponse:
    if os.getenv('READ_APPEND_ONLY') == 'true':
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={'details': 'You are in read_append_only mode, you can only read and add templates/blueprints. Update operations are not allowed'}
        )
    try:
        with open(BLUEPRINT_FILEPATH) as b:
            blueprints = yaml.safe_load(b.read())

        _, blueprints[blueprint_id] = blueprints[blueprint_id], {k:v for k,v in blueprint.model_dump().items() if k != 'name'}

        with open(BLUEPRINT_FILEPATH, 'w') as b:
            yaml.dump(blueprints, b)

        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=blueprints
        )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Mandatory Blueprints file {BLUEPRINT_FILEPATH} not found',}
            )
    except KeyError as e:
        status_code = status.HTTP_404_NOT_FOUND

        logger.info(e)
        return JSONResponse(
            status_code = status_code,
            content={'details': f'Blueprint {blueprint_id} not found',}
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.get('/templates/{template_id}', status_code=200, tags=['Templates'], description='Get a specific template')
def get_template(template_id: str,) -> JSONResponse:
    try:
        if template_id == 'blueprints':
            raise ValueError('Template filename should be different from Blueprint filename')

        return FileResponse(
            path=f'{TEMPLATES_DIRPATH}/{template_id}.yaml',
            filename='{template_id}.yaml'
        )
    except ValueError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_409_CONFLICT,
                content={'details': f'Template filename should be different from Blueprint filename',}
            )
    except FileNotFoundError as e:
        logger.info(e)

        return JSONResponse(
                status_code = status.HTTP_501_NOT_IMPLEMENTED,
                content={'details': f'Template file {TEMPLATES_DIRPATH}/{template_id}.yaml not found',}
            )
    except KeyError as e:
        status_code = status.HTTP_404_NOT_FOUND

        logger.info(e)
        return JSONResponse(
            status_code = status_code,
            content={'details': f'Template {template_id} not found',}
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.get('/templates', status_code=200, tags=['Templates'], description='Get available templates list')
def get_templates() -> JSONResponse:
    try:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'path': TEMPLATES_DIRPATH,
                'templates': [t for t in env.list_templates() if t != '__blueprints.yaml']
            }
        )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )

@app.post('/templates', status_code=201, tags=['Templates'], description='Upload a new template file')
async def add_template(template: UploadFile) -> JSONResponse:
    already_exists = False
    try:
        templates = [t for t in env.list_templates() if t != '__blueprints.yaml']

        if template.filename == '__blueprints.yaml':
            raise ValueError('Template filename should be different from Blueprint filename')
        if template.filename in templates:
            already_exists = True
            raise ValueError(f'Template name {template.filename} already exists. try with a different one')

        with open(f'{TEMPLATES_DIRPATH}/{template.filename}', 'wb') as t:
            t.write(template.file.read())

        return JSONResponse(
            status_code = status.HTTP_201_CREATED,
            content={
                'details': f'Template {TEMPLATES_DIRPATH}/{template.filename} successfully added',
                'templates': [t for t in env.list_templates() if t != '__blueprints.yaml'],
                }
        )
    except ValueError as e:
        logger.info(e)
        status_code = status.HTTP_409_CONFLICT

        if already_exists:
            return JSONResponse(
                    status_code = status_code,
                    content={'details': f'Template name {template.filename} already exists. Try with a different one',}
                )
        else:
            return JSONResponse(
                    status_code = status_code,
                    content={'details': f'Template filename should be different from Blueprint filename',}
                )
    except Exception as e:
        logger.exception(e)

        return JSONResponse(
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'details': 'Unexpected Internal Server Error Occurred, Please open an issue about this bug: https://github.com/soubinan/ignition-server/issues/new/choose',}
        )
