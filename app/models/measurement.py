from datetime import datetime
from sqlalchemy import Column, Integer, Float, DateTime
from app.core.database import Base


class Measurement(Base):
    """
    SQLAlchemy model for storing solar position measurements.
    Each record captures a comparison between device sensor readings
    and calculated NASA/Pysolar sun position.
    """

    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Location where measurement was taken
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Device sensor readings (what the user measured)
    device_azimuth = Column(Float, nullable=False)
    device_altitude = Column(Float, nullable=False)

    # Calculated sun position (from Pysolar)
    nasa_azimuth = Column(Float, nullable=False)
    nasa_altitude = Column(Float, nullable=False)

    # Delta between device and calculated values
    delta_azimuth = Column(Float, nullable=False)
    delta_altitude = Column(Float, nullable=False)

    def __repr__(self):
        return f"<Measurement(id={self.id}, lat={self.latitude}, lon={self.longitude}, delta_az={self.delta_azimuth}, delta_alt={self.delta_altitude})>"
