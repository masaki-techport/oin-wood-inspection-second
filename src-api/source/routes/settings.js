const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');
const ini = require('ini');

/**
 * GET /api/settings
 * Returns the settings from settings.ini
 */
router.get('/', (req, res) => {
  try {
    // Read the settings.ini file
    const settingsPath = path.join(__dirname, '..', 'settings.ini');
    const settingsContent = fs.readFileSync(settingsPath, 'utf8');

    // Parse the INI file
    const settings = ini.parse(settingsContent);

    // Return the settings as JSON
    res.json(settings);
  } catch (error) {
    console.error('Error reading settings.ini:', error);
    res.status(500).json({
      error: 'Failed to read settings',
      message: error.message
    });
  }
});

module.exports = router;