const express = require('express');
const bodyParser = require('body-parser');
const cors = require('cors');
const fs = require('fs');
const { exec } = require('child_process');

const app = express();
const port = 3001;

app.use(cors());
app.use(bodyParser.json());

// Used for receive client POST data
// And call the python program
// If you want to display the command prompt window, you can change "exec" to "execSync

app.post('/api/postData', (req, res) => {
  const postData = req.body;
  console.log('Received POST data:', postData);

  // Write data to file
  fs.writeFile('temp_parameters.txt', JSON.stringify(postData), (err) => {
    if (err) {
      console.error('Error writing file:', err);
      res.status(500).json({ error: 'Failed to write data to file.' });
    } else {
      console.log('Data written to file successfully.');
      // Execute the Python script after writing the file
      try {
        exec('python main.py');
        console.log('Command executed successfully.');
        res.json({ message: 'Fetch process is performing now.' });
      } catch (error) {
        console.error(`Error executing command: ${error}`);
        res.status(500).json({ error: 'Failed to execute the command.' });
      }
    }
  });
});


app.listen(port, () => {
  console.log(`Server is running on port ${port}`);
});
