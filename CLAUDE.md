# SMB Share Wizard

A cross-platform command-line wizard for configuring SMB (Samba) shares on Windows, Linux, and macOS.

## Project Status
**Current State:** Prototype / Simulated implementation. 
The core logic exists but currently prints what it *would* do instead of executing actual system commands.

## Key Files
- smb-share-wizard/src/main.py: The main entry point and primary logic for the wizard. Handles user input collection and platform-specific \"execution\" (currently simulated).
- smb-share-wizard/src/writer.py: A utility script used to generate or update main.py.

## Progress & Features
- [x] Basic user input collection (Share name, Path, Username, Password).
- [x] Platform detection (Windows, Linux, macOS).
- [x] Simulated Windows configuration (PowerShell commands).
- [x] Simulated Linux configuration (Samba config modification).
- [x] Simulated macOS configuration.
- [x] **Cross-platform UX: Directory selection via GUI (tkinter) if available.**

## TODOs
- [ ] **Implement Real Execution:** Replace simulated prints with actual subprocess.run calls for Windows (PowerShell) and Linux (Samba/systemctl).
- [ ] **Cross-platform UX Improvement:** 
    - User management (adding multiple users/pass/credentials).
- [ ] **Permission Handling:** Add logic to check for administrative/sudo privileges before proceeding.
- [ ] **Advanced Configuration:** 
    - Support for Guest access.
    - Customizable permissions (Read-only vs Read/Write).
    - Option to specify multiple users.
- [ ] **UI Improvements:** Enhance the CLI interface (perhaps using ich or a similar library for better formatting and progress bars).
- [ ] **Error Recovery:** Implement robust error handling and rollback mechanisms if a step fails.

## Development Notes
- The project uses standard Python libraries (os, platform, subprocess, getpass).
- Always ensure that actual command execution is wrapped in appropriate error handling to prevent system instability.
