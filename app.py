#!/bin/env python
import os
from datetime import datetime
import subprocess

import tornado.ioloop
import tornado.web

dir_path = os.path.dirname(os.path.realpath(__file__))

last_develop = ''
current_task = None
tasks = []
results = []

class Task:
    def __init__(self, name, branch):
        self.name = name
        self.branch = branch
        self.stats = ''
        self.time = datetime.now().isoformat()

    def __repr__(self):
        return "{} ({})".format(self.name, self.branch)

    def __str__(self):
        return "{} ({})".format(self.name, self.branch)

    def render(self):
        out = '{} ({})  <a href={}>output</a> <br>'.format(
                self.name, self.branch, self.dirname + '/out.txt')
        out = out + self.stats
        return out

    @property
    def dirname(self):
        return os.path.join('output', self.name, self.branch, self.time)


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
    try:
        os.makedirs(current_task.dirname)
    except:
        pass

    out = open(os.path.join(current_task.dirname, 'out.txt'), 'w')
    current_task.process = tornado.process.Subprocess(
        ['/bin/bash', 'run_test.sh', current_task.branch, current_task.dirname, last_develop],
        stderr=out, stdout=out)
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
        print('Last Develop: {}'.format(last_develop))
        results_str = ''.join( '<li>{}</li>'.format(task.render()) for task in reversed(results))
        queued_str = ''.join( '<li>{}</li>'.format(task) for task in tasks)

        if current_task is not None:
            self.write(template.format(current_task.render(), queued_str, results_str))
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

class FileHandler(tornado.web.RequestHandler):
    def get(self, path):
        print(path)
        with open(os.path.join('output', path)) as f:
            self.write("<pre>")
            data = f.read()
            print(data)
            self.write(data)
            self.write("</pre>")
        self.set_header('Content-Type', 'text/html')


if __name__ == "__main__":

    # load previous
    for name in os.listdir(os.path.join(dir_path, 'output')):
        if not os.path.isdir(os.path.join(dir_path, 'output', name)):
            continue

        for branch in os.listdir(os.path.join(dir_path, 'output', name)):
            if not os.path.isdir(os.path.join(dir_path, 'output', name, branch)):
                continue

            for t in os.listdir(os.path.join(dir_path, 'output', name, branch)):
                if not os.path.isdir(os.path.join(dir_path, 'output', name, branch, t)):
                    continue

                old_task = Task(name, branch)
                old_task.time = t
                results.append(old_task)

    results = sorted(results, key=lambda task: task.time)
    for result in reversed(results):
        if result.branch == 'develop':
            last_develop = result.dirname
            break

    print("Loaded: {}".format(results))

    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/submit", SubmitHandler),
        (r'/output/(.*)', FileHandler),

    ])
    #], autoreload=True)

    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
