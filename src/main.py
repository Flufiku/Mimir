import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image
import threading
import sys
import os

class MimirApp:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_widgets()
        self.setup_tray()
        # Start tray icon immediately
        self.start_tray()
        
    def setup_window(self):
        """Configure the main window"""
        self.root.title("Mimir")
        self.root.geometry("540x360")
        self.root.resizable(True, True)
        
        # Set window icon using the ICO file
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
        self.root.iconbitmap(icon_path)
        
        # Keep window always on top
        self.root.attributes('-topmost', True)
        
        # Handle window close event to minimize to tray instead of closing
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)
        
    def setup_widgets(self):
        """Create and arrange the GUI widgets"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for resizing
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Text input label
        ttk.Label(main_frame, text="Enter text:").grid(row=0, column=0, sticky=tk.W, pady=(0, 5))
        
        # Text input field
        self.text_entry = ttk.Entry(main_frame, width=40)
        self.text_entry.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Bind Enter key to send button
        self.text_entry.bind('<Return>', lambda event: self.send_text())
        
        # Send button
        self.send_button = ttk.Button(main_frame, text="Send", command=self.send_text)
        self.send_button.grid(row=2, column=0, sticky=tk.W)
        
        # Status label to show sent messages
        self.status_label = ttk.Label(main_frame, text="Ready to send messages...")
        self.status_label.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        
        # Focus on text entry
        self.text_entry.focus()
        
    def setup_tray(self):
        """Setup system tray icon and menu"""
        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        # Load icon from ICO file for system tray
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
        tray_image = Image.open(icon_path)
        
        # Create tray icon with left-click functionality
        self.tray_icon = pystray.Icon("MimirApp", tray_image, "Mimir", menu)
        
    def start_tray(self):
        """Start the tray icon in a separate thread"""
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        
    def send_text(self):
        """Handle send button click"""
        text = self.text_entry.get().strip()
        
        if not text:
            return
            
        # Here you can add your logic to handle the sent text
        # For now, we'll just display it in the status label
        self.status_label.config(text=f"Sent: {text}")
        
        # Clear the input field
        self.text_entry.delete(0, tk.END)
        
        # Show success message
        print(f"Message sent: {text}")  # You can replace this with actual sending logic
        
    def minimize_to_tray(self):
        """Minimize window to system tray"""
        self.root.withdraw()  # Hide the window
            
    def show_window(self, icon=None, item=None):
        """Show window from system tray"""
        self.root.deiconify()  # Show the window
        self.root.lift()  # Bring to front
        self.root.attributes('-topmost', True)  # Ensure it stays on top
        
    def quit_app(self, icon=None, item=None):
        """Completely quit the application"""
        if hasattr(self, 'tray_icon'):
            self.tray_icon.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit()
        
    def run(self):
        """Start the application"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.quit_app()

if __name__ == "__main__":
    app = MimirApp()
    app.run()