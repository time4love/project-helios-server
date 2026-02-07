-- Project Helios Database Schema
-- Run this script in Supabase SQL Editor to create the required tables

-- Measurements table: stores solar position measurements
CREATE TABLE IF NOT EXISTS measurements (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,

    -- Anonymous device identifier for rate limiting
    device_id VARCHAR(255),

    -- Location where measurement was taken
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,

    -- Device sensor readings (what the user measured)
    device_azimuth DOUBLE PRECISION NOT NULL,
    device_altitude DOUBLE PRECISION NOT NULL,

    -- Calculated sun position (from Pysolar)
    nasa_azimuth DOUBLE PRECISION NOT NULL,
    nasa_altitude DOUBLE PRECISION NOT NULL,

    -- Delta between device and calculated values
    delta_azimuth DOUBLE PRECISION NOT NULL,
    delta_altitude DOUBLE PRECISION NOT NULL
);

-- Index on device_id for efficient rate limiting queries
CREATE INDEX IF NOT EXISTS idx_measurements_device_id ON measurements(device_id);

-- Index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_measurements_created_at ON measurements(created_at DESC);
