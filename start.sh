#!/bin/bash

export FLASK_APP=application
export FLASK_ENV=development
flask run -h 0.0.0.0 -p 80 --no-reload
#gotta disable reloading, otherwise multiple backends will be started at once and can cause errors
#add --no-debugger if this application is open networks with untrusted users