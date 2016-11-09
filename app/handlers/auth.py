#!/usr/bin/env python
# coding: utf-8

# LINC is an open source shared database and facial recognition
# system that allows for collaboration in wildlife monitoring.
# Copyright (C) 2016  Wildlifeguardians
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# For more information or to contact visit linclion.org or email tech@linclion.org

from tornado.web import asynchronous
from tornado.gen import coroutine
from handlers.base import BaseHandler
from datetime import datetime,timedelta
from lib.tokens import gen_token,token_encode,token_decode
from lib.rolecheck import api_authenticated
from tornado.escape import utf8
from tornado import web
from json import dumps

class CheckAuthHandler(BaseHandler):
    @api_authenticated
    def get(self):
        x_real_ip = self.request.headers.get("X-Real-IP")
        remote_ip = x_real_ip or self.request.remote_ip
        output = {
            'login ip':self.current_user['ip'],
            'check ip':remote_ip,
        }
        self.response(200,'Token valid and the user '+self.current_user['username']+' is still logged.',output)

class LoginHandler(BaseHandler):
    @asynchronous
    @coroutine
    def post(self):
        if 'username' in self.input_data.keys() and \
           'password' in self.input_data.keys():
            username = utf8(self.input_data['username'])
            password = utf8(self.input_data['password'])
            wlist = self.settings['wait_list']
            count = self.settings['attempts']
            ouser = yield self.settings['db'].users.find_one({'email':username})
            if username in wlist.keys():
                dt = wlist[username]
                if datetime.now() < dt + timedelta(minutes=30):
                    self.response(401,'Authentication failed, your user have more than 3 attempts so you must wait 30 minutes since your last attempt.')
                    return
                else:
                    del wlist[username]
            if ouser:
                if self.checkPassword(utf8(password),utf8(ouser['encrypted_password'])):
                    # Ok: password matches
                    x_real_ip = self.request.headers.get("X-Real-IP")
                    remote_ip = x_real_ip or self.request.remote_ip
                    if ouser['admin']:
                        role = 'admin'
                    else:
                        role = 'user'
                    org = yield self.settings['db'].organizations.find_one({'iid':ouser['organization_iid']})
                    orgname = ''
                    if org:
                         orgname = org['name']
                    token = gen_token()
                    objuser = { 'id': ouser['iid'],
                                'username':ouser['email'],
                                'orgname':orgname,
                                'org_id':ouser['organization_iid'],
                                'role': role,
                                'token': gen_token(36),
                                'ip':remote_ip,
                                'timestamp':datetime.now().isoformat()}
                    # update user info about te login
                    datupd = {'$set':{'updated_at':datetime.now(),
                                      'sign_in_count':int(ouser['sign_in_count'])+1,
                                      'last_sign_in_ip':ouser['current_sign_in_ip'],
                                      'last_sign_in_at':ouser['current_sign_in_at'],
                                      'current_sign_in_at':datetime.now(),
                                      'current_sign_in_ip':remote_ip
                                      }
                             }
                    upduser = self.settings['db'].users.update({'iid':ouser['iid']},datupd)
                    authtoken = web.create_signed_value(self.settings['cookie_secret'],'authtoken',dumps(objuser))
                    if username in wlist.keys():
                        del wlist[username]
                    if username in count.keys():
                        del count[username]
                    self.settings['tokens'][username] = { 'token' : authtoken, 'dt' : datetime.now() }
                    # Encode to output
                    outputtoken = token_encode(authtoken,self.settings['token_secret'])
                    # Output Response
                    self.set_header('Linc-Api-AuthToken',outputtoken)
                    self.set_status(200)
                    outputdata = {'status':'success','message':'Autentication OK.','token':outputtoken,
                                  'role':role,'orgname':orgname,
                                  'id': ouser['iid'],
                                  'organization_id': ouser['organization_iid']}
                    self.finish(outputdata)
                else:
                    # wrong password
                    if username in count.keys() and datetime.now() < count[username]['d'] + timedelta(minutes=30):
                        count[username]['c'] += 1
                    else:
                        count[username] = {'c' : 1, 'd' : None}
                    count[username]['d'] = datetime.now()
                    if count[username]['c'] > 3:
                        wlist[username] = datetime.now()
                        self.response(401,'Authentication failure, and you have more than three attempts in 30 minutes, so you will need to wait 30 minutes to try to login again.')
                    else:
                        self.response(401,'Authentication failure, password incorrect.')
            else:
                self.response(401,'Authentication failure. Username or password are incorrect or maybe the user are disabled.')
        else:
            self.response(400,'Authentication requires username and password')

class LogoutHandler(BaseHandler):
    @api_authenticated
    def post(self):
        print(self.settings['attempts'])
        print(self.settings['tokens'])
        print(self.settings['wait_list'])
        if self.current_user['username'] in self.settings['tokens'].keys():
            del self.settings['tokens'][self.current_user['username']]
            self.response(200,'Logout OK.')
        else:
            self.response(400,'Authentication token invalid. User already logged off.')
