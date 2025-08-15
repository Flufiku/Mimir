import tkinter as tk
from tkinter import ttk, messagebox
import pystray
from PIL import Image
import threading
import sys
import os
import json
import keyboard
from llama_cpp import Llama

class MimirApp:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_widgets()
        self.setup_tray()
        self.setup_global_hotkey()
        self.start_tray()
        
        # LLM setup - model will be loaded based on config
        self.llm = None
        
        # Check if we should pre-load the model
        try:
            keep_loaded = self.get_config_value("keep_model_loaded")
            if keep_loaded:
                threading.Thread(target=self.init_llm, daemon=True).start()
        except:
            pass  # If config fails, just continue without pre-loading
        
    def get_config_value(self, key):
        """Get a value from config.json, raise error if key doesn't exist"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            if key not in config:
                raise KeyError(f"Configuration key '{key}' not found in config.json")
            return config[key]
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in configuration file: {e}")
        
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
        # Configure root window grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        
        # Create both frames but only show one at a time
        self.create_input_frame()
        self.create_output_frame()
        
        # Show input frame initially
        self.show_input_page()
        
    def setup_tray(self):
        """Setup system tray icon and menu"""
        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Show", self.show_window, default=True),
            pystray.MenuItem("Hide", self.minimize_to_tray),
            pystray.MenuItem("Quit", self.quit_app)
        )
        
        # Load icon from ICO file for system tray
        icon_path = os.path.join(os.path.dirname(__file__), 'assets', 'icon.ico')
        tray_image = Image.open(icon_path)
        
        self.tray_icon = pystray.Icon("MimirApp", tray_image, "Mimir", menu)
        
    def setup_global_hotkey(self):
        """Setup global hotkey to show window and focus text entry"""
        try:
            # Get the hotkey from config
            hotkey = self.get_config_value("open_text_key")
            keyboard.add_hotkey(hotkey, self.show_window_and_focus)
            print(f"Global hotkey '{hotkey}' registered successfully")
        except Exception as e:
            print(f"Failed to setup global hotkey: {e}")
    
    def show_window_and_focus(self):
        """Show window from minimization/tray and focus on text entry"""
        def _show_and_focus():
            # Show the window
            self.root.deiconify()  # Show the window if minimized
            self.root.lift()  # Bring to front
            self.root.attributes('-topmost', True)  # Ensure it stays on top
            
            # Make sure we're on the input page
            self.show_input_page()
            
            # Focus on the text entry widget
            self.text_entry.focus_set()
            
        # Schedule the UI update on the main thread
        self.root.after(0, _show_and_focus)
        
    def start_tray(self):
        """Start the tray icon in a separate thread"""
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        
    def send_text(self):
        """Handle send button click"""
        text = self.text_entry.get("1.0", tk.END).strip()
        
        if not text:
            return
        
        # Show output page and indicate generation
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        
        # Check if model needs to be loaded
        keep_loaded = self.get_config_value("keep_model_loaded")
        if self.llm is None and not keep_loaded:
            self.output_text.insert(tk.END, "Loading model and generating...")
        else:
            self.output_text.insert(tk.END, "Generating...")
        
        self.output_text.config(state=tk.DISABLED)
        
        # Clear input text
        self.text_entry.delete("1.0", tk.END)
        
        # Show output page
        self.show_output_page()
        
        # Generate in background to keep UI responsive
        threading.Thread(target=self._generate_and_update, args=(text,), daemon=True).start()
        
    def send_text_from_key(self, event):
        """Handle Enter key press in text field"""
        self.send_text()
        return "break"  # Prevent default Enter behavior
        
    def create_input_frame(self):
        """Create the input page frame"""
        self.input_frame = ttk.Frame(self.root, padding="10")
        
        # Configure grid weights for resizing
        self.input_frame.columnconfigure(0, weight=1)  # Make column 0 expandable
        self.input_frame.columnconfigure(1, weight=0)  # Keep column 1 fixed
        self.input_frame.rowconfigure(0, weight=1)     # Make row 0 (text field area) expandable
        self.input_frame.rowconfigure(1, weight=0)     # Keep row 1 (buttons) fixed
        
        # Text input field - spans most of the window
        self.text_entry = tk.Text(self.input_frame, wrap=tk.WORD)
        self.text_entry.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Bind Enter key to send button (Shift+Enter and Ctrl+Enter for new line)
        self.text_entry.bind('<Return>', lambda event: self.send_text_from_key(event))
        self.text_entry.bind('<Shift-Return>', lambda event: self.text_entry.insert(tk.INSERT, '\n'))
        self.text_entry.bind('<Control-Return>', lambda event: self.text_entry.insert(tk.INSERT, '\n'))
        
        # Close button (bottom left)
        self.close_button = ttk.Button(self.input_frame, text="Close", command=self.quit_app)
        self.close_button.grid(row=1, column=0, sticky=tk.W)
        
        # Send button (bottom right)
        self.send_button = ttk.Button(self.input_frame, text="Send", command=self.send_text)
        self.send_button.grid(row=1, column=1, sticky=tk.E)
        
    def create_output_frame(self):
        """Create the output page frame"""
        self.output_frame = ttk.Frame(self.root, padding="10")
        
        # Configure grid weights for output page
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.columnconfigure(1, weight=0)
        self.output_frame.rowconfigure(0, weight=1)
        self.output_frame.rowconfigure(1, weight=0)
        
        # Output text field
        self.output_text = tk.Text(self.output_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.output_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Close button (bottom right)
        self.close_output_button = ttk.Button(self.output_frame, text="Close", command=self.quit_app)
        self.close_output_button.grid(row=1, column=0, sticky=tk.W)
        
        # Back button (bottom left)
        self.back_button = ttk.Button(self.output_frame, text="Back", command=self.show_input_page)
        self.back_button.grid(row=1, column=1, sticky=tk.E)


    def show_input_page(self):
        """Show the input page frame"""
        self.output_frame.grid_remove()  # Hide output frame
        self.input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))  # Show input frame
        self.text_entry.focus()  # Focus on text entry
        
    def show_output_page(self):
        """Show the output page frame"""
        self.input_frame.grid_remove()  # Hide input frame
        self.output_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))  # Show output frame 
        
    def minimize_to_tray(self):
        """Minimize window to system tray"""
        self.root.withdraw()  # Hide the window
            
    def show_window(self, icon=None, item=None):
        """Show window from system tray"""
        self.root.deiconify()  # Show the window
        self.root.lift()  # Bring to front
        self.root.attributes('-topmost', True)  # Ensure it stays on top
        
    def init_llm(self):
        """Load the GGUF model for CPU operation"""
        try:
            model_path = self.get_config_value("llm_gguf_path")
            n_ctx = self.get_config_value("llm_n_ctx")
            n_threads = self.get_config_value("llm_n_threads")
            f16_kv = self.get_config_value("llm_f16_kv")
            n_batch = self.get_config_value("llm_n_batch")
            n_ubatch = self.get_config_value("llm_n_ubatch")
            
            # Use all CPU cores if n_threads is 0
            if n_threads == 0:
                n_threads = os.cpu_count() or 4
            
            self.llm = Llama(
                model_path=model_path,
                n_ctx=n_ctx,
                n_threads=n_threads,
                f16_kv=f16_kv,
                n_batch=n_batch,
                n_ubatch=n_ubatch,
                verbose=False,
            )
                
        except Exception as e:
            self.llm = None
            print(f"LLM Load Error: {e}")
            self.root.after(0, lambda: messagebox.showerror("LLM Load Error", str(e)))
            
    def _generate_and_update(self, prompt: str):
        """Run inference and push result back to UI thread"""
        # Check if we should keep model loaded
        keep_loaded = self.get_config_value("keep_model_loaded")
        
        # Load model if not already loaded
        if self.llm is None:
            try:
                self.init_llm()
            except Exception as e:
                result = f"Failed to load model: {e}"
                def _update():
                    self.output_text.config(state=tk.NORMAL)
                    self.output_text.delete("1.0", tk.END)
                    self.output_text.insert(tk.END, result)
                    self.output_text.config(state=tk.DISABLED)
                self.root.after(0, _update)
                return
        
        if self.llm is None:
            result = "Model failed to load."
        else:
            try:
                # Get configuration values
                system_prompt = self.get_config_value("llm_system_prompt")
                max_tokens = self.get_config_value("llm_max_tokens")
                temperature = self.get_config_value("llm_temperature")
                top_p = self.get_config_value("llm_top_p")
                
                # Format prompt with ChatML format
                full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
                
                res = self.llm.create_completion(
                    prompt=full_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                result = res["choices"][0]["text"].strip()
            except Exception as e:
                result = f"Generation error: {e}"
            
            # Unload model if keep_model_loaded is False
            if not keep_loaded:
                self.llm = None
        
        # Update UI on main thread
        def _update():
            self.output_text.config(state=tk.NORMAL)
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert(tk.END, result)
            self.output_text.config(state=tk.DISABLED)
        self.root.after(0, _update)
        
    def quit_app(self, icon=None, item=None):
        """Completely quit the application"""
        # Cleanup global hotkey
        try:
            keyboard.unhook_all_hotkeys()
        except Exception as e:
            print(f"Failed to cleanup hotkeys: {e}")
            
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