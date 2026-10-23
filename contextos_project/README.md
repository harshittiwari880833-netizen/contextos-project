# ContextOS — local Flask starter project

A local prototype for importing a ChatGPT data export, reviewing possible memory facts, storing selected memories, and downloading a text context pack for use with another AI such as Gemini.

## Important limitation
This project does **not** log in to ChatGPT or Gemini and does **not** automatically sync future conversations. The import flow requires a ChatGPT export ZIP or `conversations.json`. Continuous automatic syncing requires supported, authorized integrations and cannot be achieved by scraping or by the `Save memory` button alone.

## Run on Windows (VS Code)
1. Extract this folder.
2. Open the `contextos_project` folder in VS Code.
3. In Terminal run:

   ```powershell
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```

4. Open `http://127.0.0.1:5000` in your browser.

## Import your ChatGPT data
1. In ChatGPT, go to Settings → Data Controls → Export Data and request an export.
2. Download the ZIP from the email when it arrives. Keep it private.
3. In ContextOS, choose the ZIP and click **Import and find suggestions**.
4. Review suggestions. These are simple pattern-based matches and may be incomplete or inaccurate. Select only facts you want to save.
5. Download the context pack and review it before sharing it with Gemini.

## Where data is stored
Selected memories are stored in `data/memories.json`. Review or delete this file if you want to clear local stored memories. The app processes the uploaded file in memory and does not save the raw uploaded export.

## Notes
- This is a learning prototype, not a production-ready secure data service.
- Do not expose the Flask debug server to the public internet.
- Do not upload sensitive/private information unless you understand and accept the privacy implications.
