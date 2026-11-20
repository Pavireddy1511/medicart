from fastapi import APIRouter, Response, status

from app.core.dependencies import CurrentUser, DbSession
from app.schemas.address import AddressCreate, AddressOut, AddressUpdate
from app.services import address_service

router = APIRouter(prefix="/addresses", tags=["addresses"])


@router.get("", response_model=list[AddressOut])
def list_addresses(user: CurrentUser, db: DbSession):
    return address_service.list_addresses(db, user)


@router.post("", response_model=AddressOut, status_code=status.HTTP_201_CREATED)
def create_address(data: AddressCreate, user: CurrentUser, db: DbSession):
    return address_service.create_address(db, user, data)


@router.put("/{address_id}", response_model=AddressOut)
def update_address(address_id: int, data: AddressUpdate, user: CurrentUser, db: DbSession):
    return address_service.update_address(db, user, address_id, data)


@router.post("/{address_id}/default", response_model=AddressOut)
def set_default(address_id: int, user: CurrentUser, db: DbSession):
    return address_service.set_default(db, user, address_id)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: int, user: CurrentUser, db: DbSession):
    address_service.delete_address(db, user, address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
