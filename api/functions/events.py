from bson.objectid import ObjectId
from flask import Blueprint, render_template, session, request, redirect, url_for, session, flash, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from functions.validations import *
from werkzeug.security import generate_password_hash, check_password_hash
import json
from api.views import session_refresh

mongo = MongoClient('mongodb+srv://Eventify:superuser@cluster0.cm2bh.mongodb.net/test')
mongo = mongo.get_database('EVdb')

def add_new_event(req):
    """adds a new event"""
    if validate_event_creation(req.get_json()):
            print('the event dict is valid')
            new_event_data = {}
            # form new dict with data from request item by item
            for item in req.get_json():
                if item == 'groups' or item == 'members':
                    continue
                new_event_data[item] = req.get_json().get(item)
    
            new_event_data['owner'] = str(session.get('user').get('_id')) # set owner
            owner_admin = {
                'user_id': new_event_data['owner'],
                'username': session.get('user').get('username'),
                'name': session.get('user').get('name'),
                'last_name': session.get('user').get('last_name'),
                'type': 'admin'
            }
            new_event_data['members'] = []
            new_event_data['members'].append(owner_admin) # set owner as member with type admin
            # create event
            obj = mongo.events.insert_one(new_event_data)
            
            # update user events in session
            if session.get('user').get('events') is None:
                session['user']['events'] = []
            session['user']['events'].append({
                'event_id': str(obj.inserted_id),
                'name': new_event_data['name'],
                'start_date': new_event_data['start_date'],
                'end_date': new_event_data['end_date'],
                'description': new_event_data['description'],
                'type': 'admin'
                })
            # update user events in db
            mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$set': {'events': session.get('user').get('events')}})
            
            # send POST request to add every group in group list to event.groups
            for group_id in req.get_json().get('groups'):
                # requests.post('http://127.0.0.1:5001/api/events/' + str(obj.inserted_id) + '/groups', json = {'group_id': group_id})
                pass
            # send post request to add every member of member list to event.members
            for item in req.get_json().get('members'):
                if item.get('user_id'):
                    #requests.post('http://127.0.0.1:5001/api/events/' + str(obj.inserted_id) + '/members', json = {'user_id': item.get('user_id')})
                    pass
                if item.get('username'):
                    #requests.post('http://127.0.0.1:5001/api/events/' + str(obj.inserted_id) + '/members', json = {'username': item.get('username')})
                    pass
            return jsonify({'status':'created'})

def delete_event(event, request):
    """deletes an event"""
    if event.get('owner') != str(session.get('user').get('_id')):
        return {'error': 'you are not the owner of the event'}
    id_list = []
    for item in event['members']:
        id_list.append(ObjectId(item))
    for item in id_list:
        mongo.users.update_one({'_id': item},
                                {'$pull': {'events': {'name': event['name']}}},False,True) # remove event from user events
    mongo.events.delete_one({'_id': event['_id']})
    
    # update session
    user_events = mongo.users.find_one({'_id': ObjectId(session.get('user').get('_id'))})['events']
    session['user']['events'] = user_events

    return {'success': 'event deleted'}

def add_event_member(event, user, req):
    """adds a member to an event"""
    user_idx = None
    print(f'event members {event.get("members")}')
    for idx, item in enumerate(event.get('members')):
        print(f'{idx}: {item}')
        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            break
    if user_idx is None:
        return {'error': 'event information only for members'}

    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    for member in event.get('members'):
        if user.get('user_id'):
            if member.get('user_id') == user.get('user_id'):
                return {'error': 'user is already in group'}
        if user.get('username'):
            if member.get('username') == user.get('username'):
                return {'error': 'user is already in group'}

    new_user_event_data = {}
    for item in req:
        new_user_event_data[item] = req.get(item)
    new_user_event_data['name'] = user.get('name')
    new_user_event_data['last_name'] = user.get('last_name')
    new_user_event_data['username'] = user.get('username')
    print('adding user to event')
    mongo.events.update_one({'_id': event['_id']}, {'$push': {'members': new_user_event_data}}, upsert=True) # push member to member list
    print('added user to event')
    event_for_user = {}
    event_for_user['event_id'] = str(event['_id'])
    event_for_user['name'] = event.get('name')
    event_for_user['date'] = event.get('date')
    # event_for_user['start_date'] = event.get('start_date')
    # event_for_user['end_date'] = event.get('end_date')
    if new_user_event_data['type'] == 'admin':
        event_for_user['type'] = 'admin'
    mongo.users.update_one({'_id': user['_id']}, {'$push': {'events': event_for_user}}) # push event to user events'
    return "user added to event"

def update_event_member(event, user, req):
    """updates an event to a member"""
    user_idx = None
    for idx, item in enumerate(event.get('members')):
        print(f'{idx}: {item}')
        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            break
    if user_idx is None:
        return {'error': 'event information only for members'}

    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    # update member type in user events
    new_type = req.get_json().get('type')
    event_at_user = {}
    event_index = None
    for idx, item in enumerate(user.get('events')):
        if item.get('user_id') == str(event['_id']):
            event_at_user = user.get('events')[idx]
            event_index = idx
            break
    mongo.users.update_one({'_id': user['_id']}, {'$set': {f'events.{event_index}.type': new_type}}) # set new type to event in user events
    # update member type in event members
    user_at = {}
    mongo.events.update_one({'_id': event['_id']}, {'$set': {f'members.{user_idx}.type': new_type}}) # set new type member in event members
    
    session_refresh()
    return {"success": "event member updated successfully"}

def delete_event_member(event, user, user_idx, req):
    """deletes a member from an event"""
    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    user_at = {}
    event_at_user = {}
    for idx, item in enumerate(event.get('members')):
        if item.get('user_id') == req.get_json().get('user_id'):
            user_at = event.get('members')[idx]

    for idx, item in enumerate(user.get('events')):
        if item.get('event_id') == str(event['_id']):
            event_at_user = user.get('events')[idx]

    if mongo.events.update_one({'_id': event['_id']},
                                {'$pull': {'members': user_at}},False,True):
        mongo.users.update_one({'_id': ObjectId(req.get_json().get('user_id'))},
                                {'$pull': {'events': event_at_user}},False,True) # remove event from user events
        if user.get('events') and len(user.get('events')) == 0:
            user.pop('events')
        return {'success': 'user removed from event'}
    else:
        return {'error': 'user not found'}

def add_event_group(group, event):
    """adds a new group and all of its members to an event"""
    user_idx = None
    for idx, item in enumerate(event.get('members')):
        print(f'{idx}: {item}')
        print(session.get('user').get('_id'))

        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            print('found user')
            break
    if user_idx is None:
        return {'error': 'event information only for members'}
    
    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    if event.get('groups'):
        if str(group['_id']) in [g['group_id'] for g in event.get('groups')]:
            return {'error': 'group is already in event'}

    group_at_event = {
        'group_id': str(group.get('_id')),
        'name': group.get('name'),
        'avatar': group.get('avatar')
    }
    event_at_group = {
        'event_id': str(event.get('_id')),
        'name': event.get('name'),
        'start_date': event.get('start_date'),
        'end_date': event.get('end_date'),
        'location': event.get('location'),
        'avatar': event.get('avatar')
    }

    # add group to event
    mongo.events.update_one({'_id': event['_id']}, {'$push': {'groups': group_at_event}}, upsert=True)
    # add event to group
    mongo.groups.update_one({'_id': group['_id']}, {'$push': {'events': event_at_group}}, upsert=True)
    user_id_list = []
    event_at_user = {}
    for member in group.get('members'):
        if member.get('user_id') in [m.get('user_id') for m in event.get('members')]:
            continue
        event_at_user = event_at_group
        event_at_user['type'] = 'guest'
        user_at_event = {
            'user_id': member.get('user_id'),
            'username': member.get('username'),
            'name': member.get('name'),
            'last_name': member.get('last_name'),
            'type': 'guest',
            'avatar': member.get('avatar')
        }
        user_id_list.append(ObjectId(member['user_id']))
        print('going to add this member from the group')
        print(user_at_event)
        mongo.events.update_one({'_id': event['_id']}, {'$push': {'members': user_at_event}})
    
    print('going to add the event to all the members from the group with update_many')
    mongo_res = mongo.users.update_many({'_id': {'$in': user_id_list}}, {'$push': {'events': event_at_user}})
    print(mongo_res)
    return {'success': 'group has been added', 'status': 201}

def delete_event_group(group, event):
    """deletes a group and all of its members from an event"""
    user_idx = None
    for idx, item in enumerate(event.get('members')):
        print(f'{idx}: {item}')
        print(session.get('user').get('_id'))

        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            print('found user')
            break
    if user_idx is None:
        return {'error': 'event information only for members'}

    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}

    group_in_event_idx = None
    evnet_in_group_idx = None
    event_at_user = {
        'event_id': str(event.get('_id')),
        'name': event.get('name'),
        'start_date': event.get('start_date'),
        'end_date': event.get('end_date'),
        'location': event.get('location'),
        'avatar': event.get('avatar')
    }

    for idx, item in enumerate(event.get('groups')):
        if str(group.get('_id')) == item.get('group_id'):
            group_in_event_idx = idx
            break
    for idx, item in enumerate(group.get('events')):
        if str(event.get('_id')) == item.get('event_id'):
            evnet_in_group_idx = idx
            break
    print(f'group_in_event_idx: {group_in_event_idx} event_in_group_idx: {evnet_in_group_idx}')

    user_id_list = []
    for member in group.get('members'):
        user_at_event = {
            'user_id': member.get('user_id'),
            'username': member.get('username'),
            'name': member.get('name'),
            'last_name': member.get('last_name'),
            'type': member.get('type'),
            'avatar': member.get('avatar')
        }
        mongo.events.update_one({'_id': event['_id']}, {'$pull': {'members': user_at_event}})
        user_id_list.append(ObjectId(member['user_id']))
    mongo.users.update_many({'_id': {'$in': user_id_list}}, { '$pull': {'events': event_at_user}})

    if mongo.events.update_one({'_id': event['_id']},
                                {'$pull': {'groups': event.get('groups')[group_in_event_idx]}},False,True): # remove group from events.group
        mongo.groups.update_one({'_id': group['_id']},
                                {'$pull': {'events': group.get('events')[evnet_in_group_idx]}},False,True) # remove event from group.events
        if group.get('events') and len(group.get('events')) == 0:
            group.pop('events')
            mongo.groups.update_one({'_id': group['_id']}, { '$unset': {'events': ""}})
        if event.get('groups') and len(event.get('groups')) == 0:
            event.pop('groups')
            mongo.event.update_one({'_id': event['_id']}, { '$unset': {'groups': ""}})
        return {'success': 'group removed from event'}
    else:
        return {'error': 'user not found'}
        