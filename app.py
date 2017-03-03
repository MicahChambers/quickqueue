#!/bin/env python
import os
from datetime import datetime
import subprocess
import time
import traceback

import tornado.ioloop
import tornado.web
import tornado.websocket

import socket

IP = [(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close())
      for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
PORT = 8888
dir_path = os.path.dirname(os.path.realpath(__file__))

current_task = None
tasks = []
results = []

class Task:

    @staticmethod
    def load(name, branch, time):
        self = Task(name, branch, t)
        self.stats = ''
        self.time = t
        self.read_stats()
        return self

    def __init__(self, name, branch, clean=True):
        self.name = name
        self.branch = branch
        self.stats = ''
        self.clean = clean
        self.time = datetime.now().isoformat().replace(':', '-')
        self.output = []
        self.status = None
        self.out_streams = []
        self.compare_dir = ''
        self.process = None
        print(self.dirname)

    def __repr__(self):
        return "{} ({})".format(self.name, self.branch)

    def __str__(self):
        return "{} ({})".format(self.name, self.branch)

    def render(self):
        if self.running:
            out = """
            <pre>{dirname}</pre>{name} ({branch})
            <a href={dirname}/out.txt>output</a>
            <a href=tail/{dirname}>tail</a>
            <font color="red">{status}</font>
            """.format(name=self.name, branch=self.branch, dirname=self.dirname,
                       status=self.status)
            #<a href=/tail/{dirname}/out.txt>tail</a> <br>
            return out
        else:
            out = """
            <pre>{dirname}</pre>{name} ({branch})
            <a href={dirname}/out.txt>output</a>
            <font color="red">{status}</font>
            <pre>{stats}</pre>
            """.format(name=self.name, branch=self.branch, dirname=self.dirname,
                       status=self.status, stats=self.stats)
            return out

    def read_stats(self):
        path = os.path.join(self.dirname, 'results.md')
        print(path)
        if os.path.exists(path):
            with open(path) as f:
                self.stats = f.read()
            self.status = 'Done'
        else:
            self.status = 'Error'

    @property
    def running(self):
        return self.process is not None

    @property
    def dirname(self):
        return os.path.join('output', self.name, self.branch, self.time)

    def write_stderr(self, data):
        self.process.stderr.read_until("\n", self.write_stderr)
        self.write_line(data)

    def write_stdout(self, data):
        self.process.stdout.read_until("\n", self.write_stdout)
        self.write_line(data)

    def write_line(self, data):
        data = data.strip()
        self.output.append(data)
        for stream in self.out_streams:
            stream.write(data + '\n')
        #print(data)
        if data.startswith('cruise_PROGRESS: '):
            print("New status: {}".format(self.status))
            self.status = data[17:]


template = """
<!DOCTYPE html>
<html>
<title>Dumb Regression Test Queue</title>

<form action="/submit" method="post" id="form1">
  Name: <input type="text" name="name">
  Branch: <input type="text" name="branch">
  Compare: <input type="text" name="compare">
  Clean? <input type="checkbox" name="clean">
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

tail_template = """
<!DOCTYPE html>
<html>
<head>
  <title>Output</title>
  <link href="//netdna.bootstrapcdn.com/twitter-bootstrap/2.3.1/css/bootstrap-combined.no-icons.min.css" rel="stylesheet">
  <script type="text/javascript" src="//ajax.googleapis.com/ajax/libs/jquery/1.8.2/jquery.min.js"></script>
</head>
<body>
  <div class="container">
    <h1>Output</h1>
    <pre>
      <div id="content">
      </div>
    </pre>
  </div>
  <script>
    var ws = new WebSocket('ws://%s:%i/log/%s');
    var $message = $('#message');
    var $content = $('#content');
    ws.onopen = function(){
      $message.attr("class", 'label label-success');
      $message.text('open');
    };
    ws.onmessage = function(ev){
      $message.attr("class", 'label label-info');
      $message.hide();
      $message.fadeIn("fast");
      $message.text('received message');
      $content.text(ev.data);
    };
    ws.onclose = function(ev){
      $message.attr("class", 'label label-important');
      $message.text(closed);
    };
    ws.onerror = function(ev){
      $message.attr("class", 'label label-warning');
      $message.text('error occurred');
    };
  </script>
</body>
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
        print(traceback.format_exc())

    current_task.process = tornado.process.Subprocess(
        ['/bin/bash', 'run_test.sh', current_task.branch, current_task.dirname,
         current_task.compare_dir, str(current_task.clean)],
        stderr=tornado.process.Subprocess.STREAM,
        stdout=tornado.process.Subprocess.STREAM)

    f = open(os.path.join(current_task.dirname, 'out.txt'), 'w')
    current_task.out_streams.append(f)
    current_task.process.set_exit_callback(on_done)
    current_task.process.stdout.read_until("\n", current_task.write_stdout)
    current_task.process.stderr.read_until("\n", current_task.write_stderr)


def kill():
    global current_task
    if current_task is not None:
        print("trying to kill process")
        current_task.process.terminate()
        current_task.process.wait()
        map(lambda x: x.close(), current_task.out_streams)
        current_task.process = None


def on_done(args):
    global current_task
    try:
        print("Done with {} ({})".format(current_task.name, current_task.branch))
        map(lambda x: x.close(), current_task.out_streams)
        current_task.process = None
        results.append(current_task)
        current_task.read_stats()
    except Exception:
        print(traceback.format_exc())

    current_task = None
    start_next()


class MainHandler(tornado.web.RequestHandler):
    def get(self):
        global current_task
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
        if (    'branch' not in request or
                'name' not in request or
                'compare' not in request):
            raise tornado.web.HTTPError(400)

        clean = 'clean' in request
        task = Task(request['name'][0], request['branch'][0], clean)
        task.status = 'Starting'
        if request['compare'][0] != '':
            task.compare_dir = request['compare'][0]
        tasks.append(task)

        if current_task is None:
            start_next()

        return self.redirect('/', status=302)

class FileHandler(tornado.web.RequestHandler):
    def get(self, path):
        with open(os.path.join('output', path)) as f:
            data = f.read()
            self.write(data)
        self.set_header('Content-Type', 'application/octet-stream')

class TailHandler(tornado.web.RequestHandler):

    def get(self, path):
        html = tail_template % (IP, PORT, path)
        print(html)
        self.write(html)


class LogStreamer(tornado.websocket.WebSocketHandler):
    def open(self, path):
        print("Log streaming:", path)
        global current_task
        self.task = None
        print(current_task.dirname)
        if current_task.dirname == path:
            self.task = current_task
            print("Opening {}".format(path))
            current_task.out_streams.append(self)
            self.buff = []

    def on_close(self, *args, **kwargs):
        if self.task is not None:
            self.task.out_streams.remove(self)

    def write(self, data):
        data = data.strip()
        self.buff.append(data)
        self.buff = self.buff[-50:]
        self.write_message('\n'.join(self.buff))


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

                old_task = Task.load(name, branch, t)
                results.append(old_task)

    results = sorted(results, key=lambda task: task.time)
    print("Loaded: {}".format(results))

    app = tornado.web.Application([
        (r"/", MainHandler),
        (r"/submit", SubmitHandler),
        (r'/tail/(.*)', TailHandler),
        (r'/log/(.*)', LogStreamer),
        (r'/output/(.*)', FileHandler),
    ], compress_response=True)
    #], autoreload=True)

    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
