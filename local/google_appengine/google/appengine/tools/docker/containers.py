#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Docker image and docker container classes."""

from collections import namedtuple

import logging


ImageOptions = namedtuple(
    'ImageOptions', [
        'dockerfile_dir',
        'tag',
        'nocache'
    ]
)
# TODO: add rm option


ContainerOptions = namedtuple(
    'ContainerOptions', [
        'image_opts',
        'port',
        'environment',
        # TODO: use another container to forward logs to
        # instead of mounting host directory.
        'volumes'
    ]
)


class Image(object):
  """Docker Image."""

  def __init__(self, docker_client, image_opts):
    self._docker_client = docker_client
    self._image_opts = image_opts
    self._image_id = None

  def Build(self):
    assert not self._image_id
    logging.info('Building image %s...', self._image_opts.tag)
    self._image_id, _ = self._docker_client.build(
        path=self._image_opts.dockerfile_dir,
        tag=self._image_opts.tag,
        quiet=False, fileobj=None, nocache=self._image_opts.nocache,
        rm=False, stream=False)
    logging.info('Image %s built.', self._image_opts.tag)

  def Remove(self):
    if self._image_id:
      self._docker_client.remove_image(self._image_id)
      self._image_id = None

  @property
  def id(self):
    return self._image_id

  def __enter__(self):
    self.Build()
    return self

  # pylint: disable=redefined-builtin
  def __exit__(self, type, value, traceback):
    self.Remove()

  def __del__(self):
    self.Remove()


class Container(object):
  """Docker Container."""

  def __init__(self, docker_client, container_opts):
    self._docker_client = docker_client
    self._container_opts = container_opts

    self._image = Image(docker_client, container_opts.image_opts)
    self._container_id = None
    self._port = None

  def Start(self):
    """Builds an image and runs a container."""
    assert not self._container_id

    self._image.Build()

    logging.info('Creating container...')
    self._container_id = self._docker_client.create_container(
        image=self._image.id, hostname=None, user=None, detach=True,
        stdin_open=False,
        tty=False, mem_limit=0,
        ports=[self._container_opts.port],
        volumes=self._container_opts.volumes.keys(),
        environment=self._container_opts.environment,
        dns=None,
        network_disabled=False, name=None)
    logging.info('Container %s created.', self._container_id)

    self._docker_client.start(
        self._container_id,
        # Assigns a random available docker port
        port_bindings={self._container_opts.port: None},
        binds=self._container_opts.volumes)

    container_info = self._docker_client.inspect_container(self._container_id)
    self._port = int(container_info['NetworkSettings']['Ports']
                     ['%d/tcp' % self._container_opts.port][0]['HostPort'])

  def Stop(self):
    """Stops a running container, removes it."""
    if self._container_id:
      self._docker_client.stop(self._container_id)
      self._docker_client.remove_container(self._container_id, v=False,
                                           link=False)
      self._container_id = None

  @property
  def host(self):
    return 'localhost'

  @property
  def port(self):
    return self._port

  @property
  def addr(self):
    return '%s:%d' % (self.host, self.port)

  def __enter__(self):
    self.Start()
    return self

  # pylint: disable=redefined-builtin
  def __exit__(self, type, value, traceback):
    self.Stop()

  def __del__(self):
    self.Stop()
