# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/sina-al/pymediate/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                            |    Stmts |     Miss |      Cover |   Missing |
|------------------------------------------------ | -------: | -------: | ---------: | --------: |
| src/pymediate/\_\_init\_\_.py                   |       12 |        0 |    100.00% |           |
| src/pymediate/\_internal/\_\_init\_\_.py        |        0 |        0 |    100.00% |           |
| src/pymediate/\_internal/event.py               |       33 |        1 |     96.97% |        65 |
| src/pymediate/\_internal/handler.py             |       85 |        2 |     97.65% |     84-85 |
| src/pymediate/\_internal/mediator.py            |       19 |        0 |    100.00% |           |
| src/pymediate/\_internal/pipeline.py            |       20 |        0 |    100.00% |           |
| src/pymediate/\_internal/registry.py            |       84 |        4 |     95.24% |184, 190, 197, 206 |
| src/pymediate/\_internal/stream.py              |       52 |        1 |     98.08% |       143 |
| src/pymediate/errors.py                         |       60 |        0 |    100.00% |           |
| src/pymediate/event.py                          |        5 |        0 |    100.00% |           |
| src/pymediate/handler.py                        |        5 |        0 |    100.00% |           |
| src/pymediate/mediator.py                       |       26 |        0 |    100.00% |           |
| src/pymediate/pipeline.py                       |       44 |        0 |    100.00% |           |
| src/pymediate/providers/\_\_init\_\_.py         |        2 |        0 |    100.00% |           |
| src/pymediate/providers/dependency\_injector.py |       38 |        0 |    100.00% |           |
| src/pymediate/request.py                        |       12 |        0 |    100.00% |           |
| src/pymediate/service.py                        |       51 |        0 |    100.00% |           |
| src/pymediate/stream.py                         |       17 |        0 |    100.00% |           |
| src/pymediate/sync/\_\_init\_\_.py              |       11 |        0 |    100.00% |           |
| src/pymediate/sync/event.py                     |        5 |        0 |    100.00% |           |
| src/pymediate/sync/handler.py                   |        5 |        0 |    100.00% |           |
| src/pymediate/sync/mediator.py                  |       29 |        0 |    100.00% |           |
| src/pymediate/sync/pipeline.py                  |       44 |        0 |    100.00% |           |
| src/pymediate/sync/stream.py                    |        7 |        0 |    100.00% |           |
| **TOTAL**                                       |  **666** |    **8** | **98.80%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/sina-al/pymediate/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/sina-al/pymediate/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/sina-al/pymediate/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/sina-al/pymediate/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2Fsina-al%2Fpymediate%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/sina-al/pymediate/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.