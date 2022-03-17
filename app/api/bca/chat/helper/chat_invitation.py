import dataclasses
import sqlalchemy as sql
import typing

import app.database as db_module
import app.database.bca.profile as profile_module
import app.database.bca.chat as chat_module

db = db_module.db


@dataclasses.dataclass
class ChatInvitableCheckReturnType:
    profile_id: int
    success: bool
    code: int
    message: str
    data: typing.Optional[dict]


def is_profile_chat_invitable(
        requested_profile_id: int,
        requested_user_id: int,
        target_room: chat_module.ChatRoom,
        target_profile: profile_module.Profile,
        check_is_user_in_room: bool = False,
        db_commit: bool = False):

    if not target_profile:
        return ChatInvitableCheckReturnType(
            profile_id=-1, success=False, code=409, message='해당 프로필을 찾지 못했습니다.',
            data={'resource_name': ['profile', ]})

    # We need to block request that tries to invite user's another profile.
    if target_profile.uuid != requested_profile_id and target_profile.user_id == requested_user_id:
        return ChatInvitableCheckReturnType(
            profile_id=target_profile.uuid, success=False, code=409,
            message='본인의 다른 프로필은 초대할 수 없습니다.',
            data={'conflict_reason': ['본인의 다른 프로필은 초대할 수 없습니다.', ]})

    # We were supposed to deny invitation of already entered user's another profile,
    # But attacker can check the user of two profiles using this role,
    # So we'll turn off this feature.
    '''
    # Check is target user in target room, notes that we need to check "USER", not "PROFILE"
    profile_participant_record = db.session.query(chat_module.ChatParticipant)\
        .filter(chat_module.ChatParticipant.room_id == target_room.uuid)\
        .filter(chat_module.ChatParticipant.user_id == target_profile.user_id)\
        .first()
    # If profile_participant_record is not None,
    # then target user is already in target room, so resource conflict.
    if profile_participant_record:
        return ChatInvitableCheckReturnType(
            profile_id=target_profile.uuid, success=False, code=409,
            message='이미 해당 프로필의 주인이 방에 들어와있습니다.',
            data={'conflict_reason': ['이미 해당 프로필의 주인이 방에 들어와있습니다.', ]})
    '''

    # Check if user tries to enter by itself, or want to invite another user.
    if target_profile.uuid == requested_profile_id and target_profile.user_id == requested_user_id:
        # OK, User tries to enter the room.
        # There can be a two results.
        #   1. Target room is not private, so target user enters the room.
        #   2. Target room is private, so permission denied.
        # Let's check it out.

        # If targer room is private, then this is case 2
        if target_room.private:
            return ChatInvitableCheckReturnType(
                profile_id=target_profile.uuid, success=False, code=403,
                message='공개되지 않은 방입니다', data={})

        # OK, this is senario 1.
        target_room.add_new_participant(target_profile, db_commit)
        return ChatInvitableCheckReturnType(
            profile_id=target_profile.uuid, success=True, code=201,
            message='입장했습니다.', data={})

    else:
        # OK, user is trying to invite other profile.
        # There can lead to multiple results.
        #   1. Requested profile is not in target room,
        #      so requested profile cannot invite target user on this room.
        #   2. Targer user is not on any relationship with requested user,
        #      2-1. If target user is not allowed to be invited by annonymous, so permission denied.
        #      2-2. Else target user is allowed to be invited by annonymous, then invitaion success.
        #   3. Requested user is on any "BLOCK" relationship with target user, so permission denied.
        #   4. Requested user is in target room, and both have a "FOLLOW" or "HIDE" relationship,
        #      so target user enters the room.

        # If requested user is not in target room, then permission denied. Senario 1.
        if check_is_user_in_room:
            req_profile_participant_record = db.session.query(chat_module.ChatParticipant)\
                .filter(chat_module.ChatParticipant.room_id == target_room.uuid)\
                .filter(chat_module.ChatParticipant.profile_id == requested_profile_id)\
                .first()
            if not req_profile_participant_record:
                return ChatInvitableCheckReturnType(
                    profile_id=target_profile.uuid, success=False, code=403,
                    message='참여하지 않은 방에 인원을 초대할 수 없습니다.', data={})

        # Now, we need to check relationship between those two profiles.
        # Let's query those relationships on a single query.
        rel_between_profiles = db.session.query(profile_module.ProfileRelation)\
            .filter(
                sql.or_(
                    sql.and_(
                        profile_module.ProfileRelation.from_profile_id == requested_profile_id,
                        profile_module.ProfileRelation.to_profile_id == target_profile.uuid, ),
                    sql.and_(
                        profile_module.ProfileRelation.to_profile_id == requested_profile_id,
                        profile_module.ProfileRelation.from_profile_id == target_profile.uuid, ), ), ).all()
        # REQUESTER -> TARGET relationship
        # req_to_target_rel = [p for p in rel_between_profiles
        #                      if p.from_profile_id == requested_profile_id
        #                      and p.to_profile_id == target_profile.uuid
        #                      and p.status != profile_module.ProfileRelationStatus.FOLLOW_REQUESTED]
        # TARGET -> REQUESTER relationship
        target_to_req_rel = [p for p in rel_between_profiles
                             if p.from_profile_id == target_profile.uuid
                             and p.to_profile_id == requested_profile_id
                             and p.status != profile_module.ProfileRelationStatus.FOLLOW_REQUESTED]

        # Check if there's any "BLOCK" relationship
        is_there_any_blocked_rel = [p for p in rel_between_profiles
                                    if p.status == profile_module.ProfileRelationStatus.BLOCK]

        # Target profile has no relationship with requested profile. This is senario 2.
        if not target_to_req_rel:
            if not target_profile.can_annonymous_invite:
                # This is senario 2-1.
                return ChatInvitableCheckReturnType(
                    profile_id=target_profile.uuid, success=False, code=403,
                    message='해당 프로필은 해당 프로필이 팔로우한 사람만 초대장을 보낼 수 있습니다.',
                    data={})

            # This is senario 2-2.
            target_room.add_new_participant(target_profile, db_commit)
            return ChatInvitableCheckReturnType(
                profile_id=target_profile.uuid, success=True, code=201,
                message='초대했습니다.', data={})

        # Requested user is on any "BLOCK" relationship with target user. This is senario 3
        elif is_there_any_blocked_rel:
            return ChatInvitableCheckReturnType(
                profile_id=target_profile.uuid, success=False, code=403,
                message='해당 프로필을 초대할 수 없습니다.', data={})

        # OK, this is senario 4.
        target_room.add_new_participant(target_profile, db_commit)
        return ChatInvitableCheckReturnType(
            profile_id=target_profile.uuid, success=True, code=201,
            message='초대했습니다.', data={})
