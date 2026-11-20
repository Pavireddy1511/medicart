from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.base import TimestampMixin
from app.models.enums import AddressType
from app.models.user import User


class Address(TimestampMixin, Base):
    __tablename__ = "addresses"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    mobile_number: Mapped[str] = mapped_column(String(15), nullable=False)
    house_building: Mapped[str] = mapped_column(String(150), nullable=False)
    street: Mapped[str] = mapped_column(String(150), nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(150), nullable=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    address_type: Mapped[str] = mapped_column(
        String(20), default=AddressType.HOME.value, nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped[User] = relationship(back_populates="addresses")

    def as_snapshot(self) -> dict:
        return {
            "recipient_name": self.recipient_name,
            "mobile_number": self.mobile_number,
            "house_building": self.house_building,
            "street": self.street,
            "landmark": self.landmark,
            "city": self.city,
            "state": self.state,
            "pincode": self.pincode,
            "address_type": self.address_type,
        }
