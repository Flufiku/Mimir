import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
        
        # Conversation history
        self.conversation_history = []  # List of tuples: (user_message, ai_response)
        
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
        
        # Create frames but only show one at a time
        self.create_input_frame()
        self.create_output_frame()
        self.create_settings_frame()
        
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
        self.input_frame.columnconfigure(0, weight=0)  # Make column 0 expandable
        self.input_frame.columnconfigure(1, weight=1)  # Keep column 1 fixed
        self.input_frame.columnconfigure(2, weight=0)  # Keep column 2 fixed
        self.input_frame.rowconfigure(0, weight=1)     # Make row 0 (text field area) expandable
        self.input_frame.rowconfigure(1, weight=0)     # Keep row 1 (buttons) fixed
        
        # Text input field - spans most of the window
        self.text_entry = tk.Text(self.input_frame, wrap=tk.WORD)
        self.text_entry.grid(row=0, column=0, columnspan=4, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Bind Enter key to send button (Shift+Enter and Ctrl+Enter for new line)
        self.text_entry.bind('<Return>', lambda event: self.send_text_from_key(event))
        self.text_entry.bind('<Shift-Return>', lambda event: self.text_entry.insert(tk.INSERT, '\n'))
        self.text_entry.bind('<Control-Return>', lambda event: self.text_entry.insert(tk.INSERT, '\n'))
        
        # Settings button (bottom center)
        self.settings_button = ttk.Button(self.input_frame, text="Settings", command=self.show_settings_page)
        self.settings_button.grid(row=1, column=0, sticky=tk.W)
        
        # New Chat button (bottom left)
        self.new_chat_button = ttk.Button(self.input_frame, text="New Chat", command=self.clear_conversation_history)
        self.new_chat_button.grid(row=1, column=1, sticky=tk.E)
        
        # Send button (bottom right)
        self.send_button = ttk.Button(self.input_frame, text="Send", command=self.send_text)
        self.send_button.grid(row=1, column=2, sticky=tk.E)
        
    def create_output_frame(self):
        """Create the output page frame"""
        self.output_frame = ttk.Frame(self.root, padding="10")
        
        # Configure grid weights for output page
        self.output_frame.columnconfigure(0, weight=1)
        self.output_frame.rowconfigure(0, weight=1)
        self.output_frame.rowconfigure(1, weight=0)
        
        # Output text field
        self.output_text = tk.Text(self.output_frame, wrap=tk.WORD, state=tk.DISABLED)
        self.output_text.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Back button (bottom right)
        self.back_button = ttk.Button(self.output_frame, text="Back", command=self.show_input_page)
        self.back_button.grid(row=1, column=0, sticky=tk.E)
        
        # Bind Enter key to back button on the root window when output frame is shown
        def on_enter_key(event):
            self.show_input_page()
            return "break"
        
        self.output_frame.on_enter_key = on_enter_key  # Store reference for later use

    def create_settings_frame(self):
        """Create the settings page frame"""
        self.settings_frame = ttk.Frame(self.root, padding="10")
        
        # Configure grid weights for settings page
        self.settings_frame.columnconfigure(0, weight=1)
        self.settings_frame.rowconfigure(0, weight=1)
        self.settings_frame.rowconfigure(1, weight=0)
        
        # Create scrollable frame for settings
        self.settings_canvas = tk.Canvas(self.settings_frame)
        self.settings_scrollbar = ttk.Scrollbar(self.settings_frame, orient="vertical", command=self.settings_canvas.yview)
        self.settings_scrollable_frame = ttk.Frame(self.settings_canvas)
        
        # Configure scrollable frame to expand properly
        self.settings_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.settings_canvas.configure(scrollregion=self.settings_canvas.bbox("all"))
        )
        
        # Bind canvas to expand with window
        self.settings_canvas.bind(
            "<Configure>",
            lambda e: self.settings_canvas.itemconfig(self.canvas_frame_id, width=e.width-20)
        )
        
        self.canvas_frame_id = self.settings_canvas.create_window((0, 0), window=self.settings_scrollable_frame, anchor="nw")
        self.settings_canvas.configure(yscrollcommand=self.settings_scrollbar.set)
        
        # Bind mouse wheel events for scrolling anywhere in the canvas area
        def _on_mousewheel(event):
            self.settings_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_to_mousewheel(event):
            self.settings_canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_from_mousewheel(event):
            self.settings_canvas.unbind_all("<MouseWheel>")
        
        # Bind mouse wheel events to canvas and scrollable frame
        self.settings_canvas.bind('<Enter>', _bind_to_mousewheel)
        self.settings_canvas.bind('<Leave>', _unbind_from_mousewheel)
        self.settings_scrollable_frame.bind('<Enter>', _bind_to_mousewheel)
        self.settings_scrollable_frame.bind('<Leave>', _unbind_from_mousewheel)
        
        self.settings_canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.settings_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Load current config and create settings widgets
        self.settings_vars = {}
        self.create_settings_widgets()
        
        # Buttons frame
        self.settings_buttons_frame = ttk.Frame(self.settings_frame)
        self.settings_buttons_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        self.settings_buttons_frame.columnconfigure(0, weight=1)
        self.settings_buttons_frame.columnconfigure(1, weight=0)
        
        # Back button (bottom left)
        self.settings_back_button = ttk.Button(self.settings_buttons_frame, text="Back", command=self.show_input_page)
        self.settings_back_button.grid(row=0, column=0, sticky=tk.W)
        
        # Save button (bottom right)
        self.settings_save_button = ttk.Button(self.settings_buttons_frame, text="Save", command=self.save_settings)
        self.settings_save_button.grid(row=0, column=1, sticky=tk.E)
        
    def create_settings_widgets(self):
        """Create individual setting widgets based on config.json"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'r') as f:
                config = json.load(f)
        except Exception as e:
            messagebox.showerror("Config Error", f"Failed to load config: {e}")
            return
        
        # Setting descriptions for tooltips
        setting_descriptions = {
            "llm_gguf_path": "Path to the GGUF model file for the LLM",
            "llm_max_tokens": "Maximum number of tokens to generate in a response",
            "llm_n_ctx": "Context window size (number of tokens the model can consider)",
            "keep_model_loaded": "Whether to keep the model loaded in memory for faster responses",
            "llm_temperature": "Controls randomness in generation (0.0 = deterministic, 1.0 = very random)",
            "llm_top_p": "Nucleus sampling parameter (probability threshold for token selection)",
            "llm_n_threads": "Number of CPU threads to use (0 = use all available)",
            "llm_f16_kv": "Use 16-bit floating point for key-value cache (saves memory)",
            "llm_n_batch": "Batch size for processing tokens",
            "llm_n_ubatch": "Micro-batch size for processing tokens",
            "llm_system_prompt": "System prompt that defines the AI assistant's behavior",
            "open_text_key": "Global hotkey to open the text input window",
            "conversation_history_length": "Number of previous message pairs to remember in conversation history"
        }
        
        # Configure the main grid for proper alignment
        self.settings_scrollable_frame.columnconfigure(0, weight=0, minsize=200)  # Fixed width for labels
        self.settings_scrollable_frame.columnconfigure(1, weight=1, minsize=300)  # Expandable for inputs
        
        row = 0
        for setting_key, setting_value in config.items():
            # Setting label with tooltip
            label = ttk.Label(self.settings_scrollable_frame, text=f"{setting_key}:")
            label.grid(row=row, column=0, sticky=(tk.W, tk.N), padx=(10, 20), pady=5)
            
            # Add tooltip
            if setting_key in setting_descriptions:
                self.create_tooltip(label, setting_descriptions[setting_key])
            
            # Create appropriate widget based on value type
            if isinstance(setting_value, bool):
                # Checkbox for boolean values
                var = tk.BooleanVar(value=setting_value)
                widget = ttk.Checkbutton(self.settings_scrollable_frame, variable=var)
                widget.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
                
            elif isinstance(setting_value, (int, float)):
                # Number entry for numeric values
                var = tk.StringVar(value=str(setting_value))
                widget = ttk.Entry(self.settings_scrollable_frame, textvariable=var, width=30)
                widget.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
                
                # Validate numeric input
                widget.configure(validate='key', validatecommand=(self.root.register(self.validate_numeric), '%P'))
                
            elif setting_key == "llm_gguf_path":
                # File picker for GGUF path
                var = tk.StringVar(value=setting_value)
                
                path_frame = ttk.Frame(self.settings_scrollable_frame)
                path_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
                path_frame.columnconfigure(0, weight=1)
                
                entry = ttk.Entry(path_frame, textvariable=var)
                entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))
                
                browse_button = ttk.Button(path_frame, text="Browse", 
                                         command=lambda: self.browse_file(var, "GGUF Files", "*.gguf"))
                browse_button.grid(row=0, column=1, sticky=tk.E)
                
                widget = path_frame
                
            else:
                # Text entry for string values
                var = tk.StringVar(value=setting_value)
                if setting_key == "llm_system_prompt":
                    # Text widget for multi-line system prompt
                    widget = tk.Text(self.settings_scrollable_frame, height=4, wrap=tk.WORD, width=50)
                    widget.insert("1.0", setting_value)
                    widget.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
                else:
                    # Regular entry for other strings
                    widget = ttk.Entry(self.settings_scrollable_frame, textvariable=var, width=30)
                    widget.grid(row=row, column=1, sticky=(tk.W, tk.E), padx=(0, 10), pady=5)
            
            # Store the variable for saving later
            self.settings_vars[setting_key] = (var if not setting_key == "llm_system_prompt" else widget, type(setting_value))
            
            row += 1


    def show_input_page(self):
        """Show the input page frame"""
        self.output_frame.grid_remove()  # Hide output frame
        self.settings_frame.grid_remove()  # Hide settings frame
        self.input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))  # Show input frame
        self.text_entry.focus()  # Focus on text entry
        
    def show_output_page(self):
        """Show the output page frame"""
        self.input_frame.grid_remove()  # Hide input frame
        self.settings_frame.grid_remove()  # Hide settings frame
        self.output_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))  # Show output frame 
        
        # Bind Enter key for back functionality and focus the frame
        self.root.bind('<Return>', self.output_frame.on_enter_key)
        self.output_frame.focus_set()
        
    def show_settings_page(self):
        """Show the settings page frame"""
        self.input_frame.grid_remove()  # Hide input frame
        self.output_frame.grid_remove()  # Hide output frame
        self.settings_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))  # Show settings frame
        
    def create_tooltip(self, widget, text):
        """Create a tooltip for a widget"""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = tk.Label(tooltip, text=text, background="lightyellow", 
                           relief="solid", borderwidth=1, font=("Arial", "8", "normal"))
            label.pack()
            
            widget.tooltip = tooltip
            
        def on_leave(event):
            if hasattr(widget, 'tooltip'):
                widget.tooltip.destroy()
                del widget.tooltip
                
        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
        
    def validate_numeric(self, value):
        """Validate numeric input"""
        if value == "":
            return True
        try:
            float(value)
            return True
        except ValueError:
            return False
            
    def browse_file(self, var, file_type, file_extension):
        """Open file browser and set the selected file path"""
        filename = filedialog.askopenfilename(
            title=f"Select {file_type}",
            filetypes=[(file_type, file_extension), ("All files", "*.*")]
        )
        if filename:
            var.set(filename)
            
    def save_settings(self):
        """Save current settings to config.json"""
        try:
            config = {}
            for setting_key, (var_or_widget, original_type) in self.settings_vars.items():
                if setting_key == "llm_system_prompt":
                    # Text widget
                    value = var_or_widget.get("1.0", tk.END).strip()
                else:
                    # StringVar, BooleanVar, etc.
                    value = var_or_widget.get()
                
                # Convert to original type
                if original_type == bool:
                    config[setting_key] = bool(value)
                elif original_type == int:
                    config[setting_key] = int(float(value)) if value else 0
                elif original_type == float:
                    config[setting_key] = float(value) if value else 0.0
                else:
                    config[setting_key] = str(value)
            
            # Save to file
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
                
            messagebox.showinfo("Settings Saved", "Settings have been saved successfully!")
            
            # Reset LLM if model path changed
            self.llm = None
            
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save settings: {e}")
            
    def clear_conversation_history(self):
        """Clear the conversation history"""
        self.conversation_history = []
    
    def create_history_prompt(self):
        """Create a prompt string from conversation history using ChatML format"""
        if not self.conversation_history:
            return ""
        
        history_prompt = ""
        for user_msg, ai_response in self.conversation_history:
            history_prompt += f"<|im_start|>user\n{user_msg}<|im_end|>\n"
            history_prompt += f"<|im_start|>assistant\n{ai_response}<|im_end|>\n"
        
        return history_prompt

    def minimize_to_tray(self):
        """Minimize window to system tray and clear conversation history"""
        self.conversation_history = []  # Clear history when minimizing
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
                
                # Create history prompt and format full prompt with ChatML format
                history_prompt = self.create_history_prompt()
                full_prompt = f"<|im_start|>system\n{system_prompt}<|im_end|>\n{history_prompt}<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
                
                res = self.llm.create_completion(
                    prompt=full_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )
                result = res["choices"][0]["text"].strip()
                
                # Add to conversation history
                self.conversation_history.append((prompt, result))
                
                # Trim history to configured length
                try:
                    max_history = self.get_config_value("conversation_history_length")
                    if len(self.conversation_history) > max_history:
                        self.conversation_history = self.conversation_history[-max_history:]
                except Exception:
                    # If config fails, default to keeping last 10 exchanges
                    if len(self.conversation_history) > 10:
                        self.conversation_history = self.conversation_history[-10:]
                        
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