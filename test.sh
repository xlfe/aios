#!/bin/bash

PYTHON=$(which python)

$PYTHON setup.py nosetests --with-doctest --doctest-options=+ELLIPSIS --debug=circe -x
