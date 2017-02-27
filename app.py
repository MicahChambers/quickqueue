#!/bin/env python
import os
from datetime import datetime
import subprocess

import tornado.ioloop
import tornado.web

import schedule

dir_path = os.path.dirname(os.path.realpath(__file__))

current_task = None
tasks = []
results = []

class Task:
    def __init__(self, name, branch):
        self.name = name
        self.branch = branch
        self.dirname = None
        self.stats = ''

    def __repr__(self):
        return "{} ({})".format(self.name, self.branch)

    def __str__(self):
        return "{} ({})".format(self.name, self.branch)

    def render(self):
        print("Rendering")
        out = '{} ({})  <a href={}>stdout</a> <a href={}>stderr</a> <br>'.format(
                self.name, self.branch, '/static/' + self.dirname + '/stdout.txt',
                '/static/' + self.dirname + '/stderr.txt')
        out = out + self.stats
        return out


template = """
<!DOCTYPE html>
<html>
<title>Dumb Regression Test Queue</title>

<form action="/submit" method="post" id="form1">
  Name: <input type="text" name="name">
  Branch: <input type="text" name="branch">
</form>
<button type="submit" form="form1" value="Submit">Submit</button>


<h1> Running </h1>
{}

<h1> Queued </h1>
<ol>{}</ol>

<h1> Done </h1>
<ol>{}</ol>

</html>
"""

def start_next():
    global current_task
    assert current_task is None

    if not tasks:
        return


    current_task = tasks.pop(0)
    current_task.dirname = os.path.join('output', datetime.now().isoformat())
    print(current_task.dirname)
    try:
        os.makedirs(current_task.dirname)
    except:
        pass

    out = open(os.path.join(current_task.dirname, 'stdout.txt'), 'w')
    err = open(os.path.join(current_task.dirname, 'stderr.txt'), 'w')
    current_task.process = tornado.process.Subprocess(
        ['/bin/bash', 'run_test.sh', current_task.branch],
        stderr=err, stdout=out)
    current_task.process.set_exit_callback(on_done)


def on_done(args):
    global current_task
    print("Done with {} ({})".format(current_task.name, current_task.branch))
    results.append(current_task)
    current_task = None
    start_next()


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        global current_task
        results_str = ''.join( '<li>{}</li>'.format(task.render()) for task in results)
        queued_str = ''.join( '<li>{}</li>'.format(task) for task in tasks)

        if current_task is not None:
            self.write(template.format(current_task, queued_str, results_str))
        else:
            self.write(template.format('None', queued_str, results_str))


class SubmitHandler(tornado.web.RequestHandler):
    def post(self):
        global current_task
        request = self.request.arguments
        if 'branch' not in request or 'name' not in request:
            abort(400)

        task = Task(request['name'][0], request['branch'][0])
        tasks.append(task)

        if current_task is None:
            start_next()

        return self.redirect('/', status=302)


if __name__ == "__main__":
    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/submit", SubmitHandler),
    ], autoreload=True, static_path=dir_path)

    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
