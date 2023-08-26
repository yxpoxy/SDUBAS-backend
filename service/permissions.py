import json
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

from model.permissions import Role, RolePrivilege, UserRole, Privilege, WorkRole
from model.db import dbSession
from type.permissions import *


def handle_superiorId(data: dict, superid: int):  # 处理父节点列表JSON
    temp_list = data['ids']
    temp_list.append(superid)
    newdata = {"ids": temp_list}
    json_string = json.dumps(newdata)
    return json_string


class roleModel(dbSession):

    def get_role_info_by_id(self, id):  # 获取角色表信息
        with self.get_db() as session:
            op = session.query(Role).filter(
                Role.id == id
            ).first()
            if op is None:
                raise HTTPException(detail="Problem not found",
                                    status_code=404)
            return op

    def get_user_role_info_by_id(self, id):  # 获取用户角色表信息
        with self.get_db() as session:
            op = session.query(Role).filter(
                Role.id == id
            ).first()
            if op is None:
                raise HTTPException(detail="Problem not found",
                                    status_code=404)
            return op

    def create(self, data: role_base):  # 创建角色
        obj_dict = jsonable_encoder(data)
        with self.get_db() as session:
            result = session.query(Role).filter_by(id=obj_dict['role_superiorId']).first()  # 处理父节点
            if result is None:
                return "父节点无效"
            temp_dict = json.loads(result.superiorListId)
            superiorListId = handle_superiorId(temp_dict, obj_dict['role_superiorId'])
            NewRole = Role(name=obj_dict['role_name'], description=obj_dict['role_name'],
                           superiorId=obj_dict['role_superiorId'], superiorListId=superiorListId, template=0, status=0,
                           has_delete=0)
            session.add(NewRole)
            session.commit()
            return NewRole.id

    def delete(self, role_name: str):  # 删除角色
        with self.get_db() as session:
            result = session.query(Role).filter_by(name=role_name).first()
            result.has_delete = 1
            session.add(result)
            session.commit()
            return 'OK'

    def attribute_user_role(self, data: attribute_role_base):  # 分配用户角色
        obj_dict = jsonable_encoder(data)
        with self.get_db() as session:
            query_result = session.query(Role).filter_by(name=obj_dict['role_name']).first()  # 依照role_name先查找角色
            if query_result:
                result_dict = RolePydantic.from_orm(query_result).dict()
                new_user_role = UserRole(role_id=result_dict['id'], user_id=obj_dict['user_id'], has_delete=0)
                session.add(new_user_role)
                session.commit()
                return new_user_role.id
            else:
                return '-1'

    def attribute_privilege(self, data: attribute_privilege_base):
        obj_dict = jsonable_encoder(data)
        with self.get_db() as session:
            UserRole_query_result = session.query(UserRole).filter_by(user_id=obj_dict['user_id']).first()  # 先从用户查到角色
            now_role_id = UserRole_query_result.role_id
            Privilege_query_result = session.query(Privilege).filter_by(
                name=obj_dict['privilege_name']).first()  # 再从角色查到权限
            if Privilege_query_result is not None:
                new_role_privilege = RolePrivilege(role_id=now_role_id, privilege_id=Privilege_query_result.id,
                                                   has_delete=0)
                session.add(new_role_privilege)
                session.commit()
                return 'OK'

    def get_son_role(self, role_list: list):
        with self.get_db() as session:
            role_set = set()
            while len(role_list) != 0:
                role_set.add(role_list[0])
                son = session.query(Role).filter(
                    Role.superiorId == role_list[0]
                ).all()
                for item in son:
                    role_list.append(item.id)
                del role_list[0]
            return role_set

    def search_role_by_user(self, user_id: int):
        with self.get_db() as session:
            user_role = session.query(UserRole.role_id).filter(
                UserRole.user_id == user_id
            ).all()
            role_ids = [row[0] for row in user_role]
            return role_ids

    def search_privilege_by_role(self, role_list: list):
        with self.get_db() as session:
            privilege_set = set()
            role_set = self.get_son_role(role_list)
            for i in role_set:
                role_privilege = session.query(RolePrivilege).filter(
                    RolePrivilege.role_id == i
                ).all()
                for item in role_privilege:
                    privilege_set.add(item.privilege_id)
            return privilege_set

    def search_work_by_role(self, role_list: list):
        with self.get_db() as session:
            work_list = []
            for i in role_list:
                work = session.query(WorkRole).filter(
                    WorkRole.role_id == i
                ).all()
                for item in work:
                    work_list.append(item.id)
            return work_list

    def check_permission(self, permission_key: str, privilege_set: set):
        with self.get_db() as session:
            for item in privilege_set:
                privilege = session.query(Privilege).filter(
                    item == Privilege.id
                ).first()
                if privilege.key == permission_key:
                    return True
            return False

    def search_service_id(self, role_list: list, service_type: int, name: str):
        with self.get_db() as session:
            service_ids = []
            role_set = self.get_son_role(role_list)
            for i in role_set:
                role_privilege = session.query(RolePrivilege).filter(
                    RolePrivilege.role_id == i
                ).all()
                for item in role_privilege:
                    privilege = session.query(Privilege).filter(
                        Privilege.id == item.privilege_id,
                        Privilege.service_type == service_type,
                        Privilege.name == name
                    ).first()
                    if privilege is not None:
                        service_ids.append(privilege.service_id)
            print(service_ids)
            return service_ids

    def search_user_id_by_service(self, service_type: int, service_id: int):
        with self.get_db() as session:
            user_list = []
            query = session.query(WorkRole, UserRole).join(
                UserRole,
                WorkRole.role_id == UserRole.role_id,
            ).filter(
                WorkRole.service_type == service_type,
                WorkRole.service_id == service_id
            )
            return query

    def search_college_default_role_id(self):
        with self.get_db() as session:
            query = session.query(WorkRole).filter(
                WorkRole.service_type == 2,
                WorkRole.service_id == None
            ).one()
            return query.role_id