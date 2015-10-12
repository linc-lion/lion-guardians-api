#!/usr/bin/env python
# -*- coding: utf-8 -*-

from tornado.web import asynchronous
from tornado.gen import coroutine
from handlers.base import BaseHandler
from models.animal import Animal

class AnimalsHandler(BaseHandler):
    """A class that handles requests about animals informartion
    """
    @asynchronous
    @coroutine
    def get(self):
        objs = yield Animal.objects.find_all()
        objs = [x.to_son() for x in objs]
        self.finish(self.json_encode(objs))
