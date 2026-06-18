-- Provision the isolated test database next to the dev database on first boot.
-- The suite migrates and targets pattern_mirror_test, so tests never read or
-- write development data. Runs only when the data volume is empty (first init).
CREATE DATABASE pattern_mirror_test;
