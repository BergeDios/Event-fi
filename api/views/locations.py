from api.views import api_views
from bson.objectid import ObjectId
from flask import Blueprint, render_template, session, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from functions.validations import *
from werkzeug.security import generate_password_hash, check_password_hash
from api.views import session_refresh
import json


mongo = MongoClient('mongodb+srv://Eventify:superuser@cluster0.cm2bh.mongodb.net/test')
mongo = mongo.get_database('EVdb')

# ---------LOCATION ROUTES----------
api_views.route('/api/locations', strict_slashes=False, methods=['GET', 'POST'])
def locations():
    """GET and POST for locations"""
    if session.get('user') is None:
        return redirect(url_for('login'))
    
    if request.method == 'GET':
        # returns location list
        user_locations = session.get('user').get('locations')
        return jsonify(user_locations)

    if request.method == 'POST':
        #create new location
        print(f'entered with {request.get_json()}')
        if session.get('user').get('type') != 'sudo':
            return {'error': 'you must be sudo in order to create a new location'}
        if validate_location_creation(request.get_json()):
            print('the location dict is valid')
            new_location_data = {}
            for item in request.get_json():
                new_location_data[item] = request.get_json()[item]

            admin_info = {
                'user_id': session.get('user').get('_id'),
                'username': session.get('user').get('username'),
                'name': session.get('user').get('name'),
                'last_name': session.get('user').get('last_name'),
                'type': 'admin'
            }
            new_location_data['admins'] = []
            new_location_data['admins'].append(admin_info) # set creator as admin
            obj = mongo.groups.insert_one(new_location_data)

            # update user locations in session
            if session.get('user').get('locations') is None:
                session['user']['locations'] = []
            session['user']['locations'].append({
                'location_id': str(obj.inserted_id),
                'name': new_location_data['name'],
                'type': 'admin'
                })

            print(session.get('user').get('locations'))
            mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'locations': session.get('user').get('locations')}})# update user groups in db

            return {'success': f'created new group: {new_location_data.get("name")}'}

@api_views.route('/api/locations/<location_id>', strict_slashes=False, methods=['GET', 'PUT', 'POST', 'DELETE'])
def single_group(location_id):
    """route for single location, get for location info"""
    if session.get('user') is None:
       return redirect(url_for('index'))

    location = mongo.locations.find_one({'_id': ObjectId(location_id)})
    if location is None:
        return {'error': 'group not found'}

    if request.method == 'GET':
        location_response = {
            'name': location.get('name'),
            'avatar': location.get('avatar'),
            'description': location.get('description'),
            'position': location.get('position')
        }
        return location_response
"""
    user_idx = None
    for idx, item in enumerate(location.get('members')):
        print(f'location admins: {idx}: {item}')
        if session.get('user').get('_id') == item.get('user_id'):
            user_idx = idx
            break
    if user_idx is None:
        return {'error': 'location information only for admins'}
"""