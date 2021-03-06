from bson.objectid import ObjectId
from flask import session, jsonify
from pymongo import MongoClient
from functions.validations import *
from api.views import session_refresh
from api import UPLOAD_FOLDER
from datetime import datetime
import os

mongo = MongoClient('mongodb+srv://Eventify:superuser@cluster0.cm2bh.mongodb.net/test')
mongo = mongo.get_database('EVdb')

def add_new_event(req):
    """adds a new event"""
    if validate_event_creation(req.get_json()):
            new_event_data = {}
            new_event_location = {}
            avatar = req.get_json().get('avatar_content')
            if avatar is None:
                return {'error': 'no avatar data'}
            if validate_image(avatar) is False:
                return {'error': 'image is not supported'}
            # form new dict with data from request item by item
            for item in req.get_json():
                if item == 'groups' or item == 'members' or item == 'avatar_content':
                    continue
                elif item == 'location':
                    location = mongo.locations.find_one({'_id': ObjectId(req.get_json().get('location'))})
                    if location is None:
                        return {'error': 'location does not exist'}
                    # data of location to appear in event.location
                    new_event_location = {
                        'location_id': str(location.get('_id')),
                        'name': location.get('name'),
                        'avatar': location.get('avatar'),
                        'position': location.get('position')
                    }
                new_event_data[item] = req.get_json().get(item)

            new_event_data['location'] = new_event_location
            new_event_data['owner'] = str(session.get('user').get('_id')) # set owner
            owner_admin = {
                'user_id': new_event_data['owner'],
                'username': session.get('user').get('username'),
                'name': session.get('user').get('name'),
                'last_name': session.get('user').get('last_name'),
                'type': 'admin',
                'avatar': session.get('user').get('avatar')
            }
            new_event_data['members'] = []
            new_event_data['members'].append(owner_admin) # set owner as member with type admin
            # create event
            obj = mongo.events.insert_one(new_event_data)

            with open(os.path.join(UPLOAD_FOLDER, 'avatars', str(obj.inserted_id)), 'w+') as file:
                file.write(avatar)
            new_event_data['avatar'] = f'/static/avatars/{str(obj.inserted_id)}'
            mongo.events.update_one({'_id': obj.inserted_id}, {'$set': {'avatar': new_event_data['avatar']}})

            # add event to loaction
            event_to_location = {
                'event_id': str(obj.inserted_id),
                'name': new_event_data.get('name'),
                'avatar': new_event_data.get('avatar'),
                'start_date': new_event_data.get('start_date'),
                'end_date': new_event_data.get('end_date')
            }
            update_location = mongo.locations.update_one({'_id': ObjectId(new_event_location['location_id'])}, {'$push': {'events': event_to_location}})
            # update user events in session
            if session.get('user').get('events') is None:
                session['user']['events'] = []
            session['user']['events'].append({
                'event_id': str(obj.inserted_id),
                'name': new_event_data['name'],
                'start_date': new_event_data['start_date'],
                'end_date': new_event_data['end_date'],
                'description': new_event_data['description'],
                'location': new_event_data['location'].get('name'),
                'type': 'admin'
                })
            # update user events in db
            update_user = mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$set': {'events': session.get('user').get('events')}})
            update_list = [obj, update_user, update_location]
            if None not in update_list:
                 mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {f'notifications': 'Has creado el evento {new_event_data["name"]}'}})
            # send POST request to add every group in group list to event.groups
            if req.get_json().get('groups') is None:
                req.get_json()['groups'] = []

            for group_id in req.get_json().get('groups'):
                group = mongo.groups.find_one({"_id": ObjectId(group_id)})
                event = mongo.events.find_one({'_id': ObjectId(obj.inserted_id)})
                add_event_group(group, event)
            # send post request to add every member of member list to event.members

            if req.get_json().get('members') is None:
                req.get_json()['members'] = []
    
            for item in req.get_json().get('members'):
                user = None
                if item.get('user_id'):
                    user = mongo.users.find_one({'_id': ObjectId(item.get('user_id'))})
                elif item.get('username'):
                    user = mongo.users.find_one({'username': item.get('username')})
                if user:
                    created_event = mongo.events.find_one({'_id': ObjectId(obj.inserted_id)})
                    add_event_member(created_event, user, {'type': 'guest'})
                else:
                    return {'error': 'user not found'}
                
            return jsonify({'status': 'created event', 'event_id': str(obj.inserted_id), 'event': event_to_location})

def delete_event(event):
    """deletes an event"""
    if event.get('owner') != str(session.get('user').get('_id')):
        return {'error': 'you are not the owner of the event'}
    id_list = []
    for item in event['members']:
        id_list.append(ObjectId(item.get('user_id')))
    update_list = []
    for item in id_list:
        result = mongo.users.update_one({'_id': item},
                                {'$pull': {'events': {'name': event['name']}}},False,True) # remove event from user events
        if result is not None:
            mongo.users.update_one({'_id': item},
                                {'$push': {'notifications': 'El evento ' + event['name'] + ' a sido eliminado'}})# add notification to user
            update_list.append(result)
    # deletes event from location
    event_at_location = {
        'event_id': str(event.get('_id')),
        'name': event.get('name'),
        'avatar': event.get('avatar'),
        'start_date': event.get('start_date'),
        'end_date': event.get('end_date')
    }
    update_location = mongo.locations.update_one({'_id': ObjectId(event.get('location').get('location_id'))}, {'$pull': {'events': event_at_location}})
    update_list.append(update_location)
    # deletes event
    delete = mongo.events.delete_one({'_id': event['_id']})
    update_list.append(delete)
    if None not in update_list:
        mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'El evento ' + event['name'] + ' a sido eliminado'}})
    # update session
    user_events = mongo.users.find_one({'_id': ObjectId(session.get('user').get('_id'))})['events']
    session['user']['events'] = user_events

    return {'success': 'event deleted'}

def add_event_member(event, user, req):
    """adds a member to an event"""
    print('entered add evnet member')
    print(f'the event to add members is: {str(event)}')
    user_idx = None
    if event.get('members'):
        for idx, item in enumerate(event.get('members')):
            if item.get('user_id') == session.get('user').get('_id'):
                user_idx = idx
                break
    # Adding new user to event hardocded
    if str(event['_id']) == "62d7375d9c8bd68c80f9c080":
        pass
    elif user_idx is None:
        print('event information only for members')
        return {'error': 'event information only for members'}

    if str(event['_id']) == "62d7375d9c8bd68c80f9c080":
        pass
    elif event.get('members').get(user_idx).get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    print(f'checking if members exist vegoe it breaks evetything: {event.get("members")}')
    for member in event.get('members'):
        if user.get('user_id'):
            if member.get('user_id') == str(user.get('_id')):
                print('user is already in group')
                return {'error': 'user is already in group'}
        if user.get('username'):
            if member.get('username') == user.get('username'):
                print('user is already in group 2')
                return {'error': 'user is already in group'}
    # forming user data to insert in event.members
    new_user_event_data = {
                'user_id': str(user.get('_id')),
                'username': user.get('username'),
                'name': user.get('name'),
                'last_name': user.get('last_name'),
                'type': req.get('type'),
                'avatar': user.get('avatar')
            }
    print(f'new user event data is: {new_user_event_data}')
    for item in req:
        new_user_event_data[item] = req.get(item)
    if req.get('type') is None:
        new_user_event_data['type'] = 'guest'
    update_event = mongo.events.update_one({'_id': event['_id']}, {'$push': {'members': new_user_event_data}}, upsert=True) # push member to member list
    # forming event data to insert in user.events
    event_for_user = {}
    event_for_user['event_id'] = str(event['_id'])
    event_for_user['name'] = event.get('name')
    event_for_user['start_date'] = event.get('start_date')
    event_for_user['end_date'] = event.get('end_date')
    event_for_user['location'] = event.get('location').get('name')
    event_for_user['type'] = new_user_event_data.get('type')
    update_user = mongo.users.update_one({'_id': user['_id']}, {'$push': {'events': event_for_user}}) # push event to user events'
    if update_event is not None and update_user is not None:
        mongo.users.update_one({'_id': user['_id']}, {'$push': {'notifications': 'Has sido agregado al evento ' + event['name']}})
        return "user added to event"
    else:
        return {'error': 'Failed, couldn\'t add user to event', 'member': new_user_event_data}
    
def update_event_member(event, user, req):
    """updates an event type to a member"""
    user_idx = None
    for idx, item in enumerate(event.get('members')):
        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            break
    if user_idx is None:
        return {'error': 'event information only for members'}

    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}
    # update member type in user events
    new_type = req.get_json().get('type')
    event_index = None
    for idx, item in enumerate(user.get('events')):
        if item.get('user_id') == str(event['_id']):
            event_index = idx
            break
    update_user = mongo.users.update_one({'_id': user['_id']}, {'$set': {f'events.{event_index}.type': new_type}}) # set new type to event in user events
    # update member type in event members
    update_event = mongo.events.update_one({'_id': event['_id']}, {'$set': {f'members.{user_idx}.type': new_type}}) # set new type member in event members
    if update_user is not None and update_event is not None:
        mongo.user.update_one({'_id': user['_id']}, {'$push': {'notifications': 'Han cambiado tus privilegios a' + new_type + ' en el evento ' + event['name']}})
        session_refresh()
        return {"success": "event member updated successfully"}
    else:
        mongo.user.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'Fallo cambiar los privilegios de ' + user['name'] + 'en el evento ' + event['name']}})
        return {'error': 'Failed, couldn\'t update event member'}
    
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
        update_user = mongo.users.update_one({'_id': ObjectId(req.get_json().get('user_id'))},
                                {'$pull': {'events': event_at_user}},False,True) # remove event from user events
        if user.get('events') and len(user.get('events')) == 0:
            user.pop('events')
    if update_user is not None:
        mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'Has eliminado a ' + user.get('name') + ' del evento ' + event['name']}})
        mongo.users.update_one({'_id': user.get('_id')}, {'$push': {'notifications': 'Has sido eliminado del evento ' + event['name']}})
        return {'success': 'user removed from event'}
    else:
        return {'error': 'user was not found or could not be removed'}

def add_event_group(group, event):
    """adds a new group and all of its members to an event"""
    user_idx = None
    for idx, item in enumerate(event.get('members')):
        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
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
        'location': event.get('location').get('name'),
        'avatar': event.get('avatar')
    }
    # add group to event
    update_list = []
    update_event = mongo.events.update_one({'_id': event['_id']}, {'$push': {'groups': group_at_event}}, upsert=True)
    update_list.append(update_event)
    if update_event is not None:
        mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'Has agregado el grupo ' + group['name'] + ' al evento ' + event['name']}})
    # add event to group
    update_group = mongo.groups.update_one({'_id': group['_id']}, {'$push': {'events': event_at_group}}, upsert=True)
    update_list.append(update_group)
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
        update_list.append(mongo.events.update_one({'_id': event['_id']}, {'$push': {'members': user_at_event}}))
    
    update_members = mongo.users.update_many({'_id': {'$in': user_id_list}}, {'$push': {'events': event_at_user}})
    if update_members is not None:
        mongo.users.update_many({'_id': {'$in': user_id_list}}, {'$push': {'notifications': 'Te han agregado al evento ' + event['name'] + ' mediante el grupo ' + group['name']}})
    update_list.append(update_members)
    if None in update_list:
        mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'No se pudo agregar el grupo ' + group['name'] + ' al evento ' + event['name']}})
        return {'error': 'group not added to event'}    
    return {'success': 'group has been added', 'status': 201}

def delete_event_group(group, event):
    """deletes a group and all of its members from an event"""
    user_idx = None
    # iterate through list of members in event to find current user idx
    for idx, item in enumerate(event.get('members')):
        if item.get('user_id') == session.get('user').get('_id'):
            user_idx = idx
            break
    if user_idx is None:
        return {'error': 'event information only for members'}

    if event.get('members')[user_idx].get('type') != 'admin':
        return {'error': 'you are not the admin of this event'}

    group_in_event_idx = None
    event_in_group_idx = None
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
            event_in_group_idx = idx
            break

    user_id_list = []
    update_list = []
    for member in group.get('members'):
        user_at_event = {
            'user_id': member.get('user_id'),
            'username': member.get('username'),
            'name': member.get('name'),
            'last_name': member.get('last_name'),
            'type': member.get('type'),
            'avatar': member.get('avatar')
        }
        if user_at_event.get('type') is None:
            user_at_event['type'] = 'guest'
        # delete every member from the group from the event.members
        update_list.append(mongo.events.update_one({'_id': event['_id']}, {'$pull': {'members': user_at_event}}))
        user_id_list.append(ObjectId(member['user_id']))
    # sacar el evento de todos los miembros del grupo
    update_users = mongo.users.update_many({'_id': {'$in': user_id_list}}, { '$pull': {'events': event_at_user}})
    if update_users is not None:
        mongo.users.update_many({'_id': {'$in': user_id_list}}, { '$push': {'message': 'Has sido eliminado del evento ' + event['name'] + ' mediante el grupo ' + group['name']}})
        update_list.append(update_users)
    if mongo.events.update_one({'_id': event['_id']},
                                {'$pull': {'groups': event.get('groups')[group_in_event_idx]}},False,True): # remove group from events.group
        update_group = mongo.groups.update_one({'_id': group['_id']},
                                {'$pull': {'events': group.get('events')[event_in_group_idx]}},False,True) # remove event from group.events
        update_list.append(update_group)
        if group.get('events') and len(group.get('events')) == 0:
            group.pop('events')
            mongo.groups.update_one({'_id': group['_id']}, { '$unset': {'events': 1}})
        if event.get('groups') and len(event.get('groups')) == 0:
            event.pop('groups')
            mongo.event.update_one({'_id': event['_id']}, { '$unset': {'groups': 1}})
        if None not in update_list:
            mongo.users.update_one({'_id': ObjectId(session.get('user').get('_id'))}, {'$push': {'notifications': 'Has borrado al grupo ' + group.get('name' + 'del evento ' + event.get('name'))}})
            return {'success': 'group removed from event'}
    else:
        return {'error': 'user not found'}

def update_event_info(event, req):
    """updates an event's info"""
    new_event_data = {}
    for item in req.get_json():
        if event['item'] != req.get_json()[item]:
            new_event_data[item] = req.get_json()[item]
    mongo.events.update_one({'_id': event['_id']}, {'$set': new_event_data})
