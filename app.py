#!/bin/env python
import os
from datetime import datetime
import subprocess
import time

import tornado.ioloop
import tornado.web
import tornado.websocket

import socket

IP = [(s.connect(('8.8.8.8', 53)), s.getsockname()[0], s.close())
      for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
PORT = 8888
dir_path = os.path.dirname(os.path.realpath(__file__))

last_develop = ''
current_task = None
tasks = []
results = []

class Task:
    def __init__(self, name, branch, clean=True):
        self.name = name
        self.branch = branch
        self.stats = ''
        self.clean = clean
        self.time = datetime.now().isoformat().replace(':', '-')

    def __repr__(self):
        return "{} ({})".format(self.name, self.branch)

    def __str__(self):
        return "{} ({})".format(self.name, self.branch)

    def render(self):
        out = """
        {name} ({branch})
        <a href={dirname}/out.txt>output</a>
        <a href=tail/{dirname}/out.txt>tail</a>
        """.format(name=self.name, branch=self.branch, dirname=self.dirname)
        #<a href=/tail/{dirname}/out.txt>tail</a> <br>
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
    <h1>tornado WebSocket example</h1>
    <hr>
      WebSocket status : <span id="message"></span>
    <hr>
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
      $content.append(ev.data);
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
        pass

    out = open(os.path.join(current_task.dirname, 'out.txt'), 'w')
    current_task.process = tornado.process.Subprocess(
        ['/bin/bash', 'run_test.sh', current_task.branch, current_task.dirname,
         last_develop, str(current_task.clean)],
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
            raise tornado.web.HTTPError(400)

        clean = 'clean' in request
        task = Task(request['name'][0], request['branch'][0], clean)
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
        print("Opening {}".format(path))
        self.proc = tornado.process.Subprocess(
            ["tail", "-f", path, "-n", "0"],
            stdout=tornado.process.Subprocess.STREAM, bufsize=1)
        self.proc.set_exit_callback(self._close)
        self.proc.stdout.read_until("\n", self.write_line)
        print("Exit")

    def _close(self, *args, **kwargs):
        print("closing")
        self.close()

    def on_close(self, *args, **kwargs):
        print("trying to kill process")
        self.proc.proc.terminate()
        self.proc.proc.wait()

    def write_line(self, data):
        print("Returning to client: %s" % data.strip())
        self.write_message(data.strip() + "<br/>")
        self.proc.stdout.read_until("\n", self.write_line)


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
        (r'/tail/(.*)', TailHandler),
        (r'/log/(.*)', LogStreamer),
        (r'/output/(.*)', FileHandler),
    ], compress_response=True)
    #], autoreload=True)

    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
