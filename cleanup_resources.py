import os
import sys
import signal
import gc
import atexit
import multiprocessing
import threading
import tempfile
import shutil

_cleaned_up = False

def _force_cleanup_multiprocessing():
    """Forcibly clean up multiprocessing resources"""
    try:
        # Try to get the resource tracker
        import multiprocessing.resource_tracker as rt
        
        # Force cleanup of the resource tracker
        if hasattr(rt, '_resource_tracker') and rt._resource_tracker is not None:
            print("Forcibly cleaning up multiprocessing resources...")
            rt._resource_tracker._stop = True
            
            # Wait for the resource tracker to stop
            if hasattr(rt._resource_tracker, 'join'):
                rt._resource_tracker.join(timeout=1.0)
                
            # Kill the thread if it's still alive
            if hasattr(rt._resource_tracker, 'is_alive') and rt._resource_tracker.is_alive():
                print("Resource tracker still alive, forcing termination...")
                if hasattr(rt._resource_tracker, '_pid'):
                    try:
                        os.kill(rt._resource_tracker._pid, signal.SIGTERM)
                    except (OSError, AttributeError):
                        pass
                
            # Clear the resource list
            if hasattr(rt, '_resource_list'):
                rt._resource_list = {}
    except (ImportError, AttributeError, ValueError) as e:
        print(f"Failed to clean multiprocessing resources: {e}")

def _cleanup_temp_dirs():
    """Clean up temporary directories"""
    try:
        # Clean up the temp directory
        temp_dir = tempfile.gettempdir()
        
        # Look for directories starting with 'tmp'
        for item in os.listdir(temp_dir):
            if item.startswith('tmp') and os.path.isdir(os.path.join(temp_dir, item)):
                try:
                    shutil.rmtree(os.path.join(temp_dir, item), ignore_errors=True)
                except (PermissionError, OSError):
                    pass
    except Exception as e:
        print(f"Failed to clean temporary directories: {e}")

def cleanup(force=False):
    """Clean up all resources before exit"""
    global _cleaned_up
    
    if _cleaned_up and not force:
        return
        
    print("Performing comprehensive resource cleanup...")
    
    # Force garbage collection first
    gc.collect()
    
    # Clean up multiprocessing resources
    _force_cleanup_multiprocessing()
    
    # Clean temporary directories
    _cleanup_temp_dirs()
    
    # Reset tempdir
    try:
        tempfile.tempdir = None
    except Exception:
        pass
    
    # Clean up threads
    try:
        for thread in threading.enumerate():
            if thread != threading.current_thread() and thread.daemon:
                try:
                    if hasattr(thread, '_stop'):
                        thread._stop()
                except (AttributeError, RuntimeError):
                    pass
    except Exception:
        pass
    
    # Mark as cleaned up
    _cleaned_up = True
    print("Resource cleanup completed")

# Register the cleanup function to run at exit
atexit.register(cleanup)

# Also set up a signal handler for SIGTERM
def sigterm_handler(signum, frame):
    cleanup(force=True)
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGTERM, sigterm_handler)
if hasattr(signal, 'SIGBREAK'):  # Windows specific
    signal.signal(signal.SIGBREAK, sigterm_handler)
signal.signal(signal.SIGINT, sigterm_handler)

if __name__ == "__main__":
    # This can be run directly to clean up resources
    cleanup(force=True)
    sys.exit(0) 