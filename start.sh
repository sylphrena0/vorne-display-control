#!/bin/bash

export FLASK_APP=flaskr
export FLASK_ENV=development
flask run -h 0.0.0.0 -p 80 --no-reload --no-debugger