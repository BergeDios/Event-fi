from bson.objectid import ObjectId
from flask import redirect, url_for, session, jsonify
from pymongo import MongoClient
from functions.validations import *
from api.views import session_refresh
from api import UPLOAD_FOLDER
import os

mongo = MongoClient('mongodb+srv://Eventify:superuser@cluster0.cm2bh.mongodb.net/test')
mongo = mongo.get_database('EVdb')

def get_user_info(user_id):
    """returns user with matching id else error"""
    if session.get('user') is None:
        return redirect(url_for('login'))
    user = mongo.users.find_one({'_id': ObjectId(user_id)})
    if user:
        user['_id'] = str(user.get('_id'))
        return jsonify(user)
    else:
        return {'error': 'user not found'}

def add_new_contact(user, req):
    """adds a new contact to the logged user"""
    new_contact = None
    if req.get_json().get('user_id'):
        new_contact = mongo.users.find_one({'_id': ObjectId(req.get_json().get('user_id'))})
    elif req.get_json().get('username'):
        new_contact = mongo.users.find_one({'username': req.get_json().get('username')})
    
    if new_contact is None:
        return {"error": "target user not found"}

    if new_contact.get('username').lower() == session.get('user').get('username'):
            return {'error': 'you can not add yourself as a contact'}

    if session.get('user').get('contacts'):
        for c in session.get('user').get('contacts'):
            if c.get('user_id') == str(user.get('_id')):
                return {'error': 'user already in contacts'}

    keys_to_pop = ['password', 'email', 'groups', 'events', 'contacts', 'notifications']
    for item in keys_to_pop:
        if new_contact.get(item):
            new_contact.pop(item)
    new_contact['user_id'] = str(new_contact['_id'])
    new_contact.pop('_id')
    # add contact in session
    if session.get('user').get('contacts') is None:
        session['user']['contacts'] = []
    for contact in session.get('user').get('contacts'):
        if req.get_json().get('user_id'):
            if contact.get('user_id') == req.get_json().get('user_id'):
                return {'error': 'you already have that contact'}
        elif req.get_json().get('username'):
            if contact.get('username') == req.get_json().get('username'):
                return {'error': 'you already have that contact'}
    session['user']['contacts'].append(new_contact)
    # add contact in db
    mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))},
                            {'$push': {'contacts': new_contact}})
    session_refresh()
    # return redirect(url_for('user'))
    # must redirect to /user in the front
    try:
        with open(os.path.join(UPLOAD_FOLDER, 'avatars', new_contact.get('user_id'))) as avt:
            print('pude abrir el avatar')
            new_contact['avatar'] = avt.read()
    except Exception as ex:
        print(ex)
    return jsonify(new_contact), 201

def delete_contact(req):
    """deletes a contact from the current logged user"""
    contact_to_delete = mongo.users.find_one({'_id': ObjectId(req.get_json().get('user_id'))})
    if contact_to_delete is None:
        return {'error': 'user does not exist'}
    keys_to_pop = ['password', 'email', 'groups', 'events', 'contacts', 'notifications']
    for item in keys_to_pop:
        if contact_to_delete.get(item) is not None:
            contact_to_delete.pop(item)
    contact_to_delete['user_id'] = str(contact_to_delete['_id'])
    contact_to_delete.pop('_id')

    # remove contact in sessioni
    if session.get('user').get('contacts'):
        try:
            session['user']['contacts'].remove(contact_to_delete)
            if len(session['user']['contacts']) == 0:
                session['user'].pop('contacts')# if no contacts left pop contacts list
        except Exception as ex:
            print(ex)
    # remove contact in db
    mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))},
                            {'$pull': {'contacts': contact_to_delete}})
    """if mongo.users.find_one({ 'contacts.0': {'$exists' : False }}):
        mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))},
                               {'$unset': {'contacts': 1}})# if no contacts left pop contact list"""
    # return redirect(url_for('user'))
    # must redirect to /user in the front
    return {"success": "contact deleted"}
