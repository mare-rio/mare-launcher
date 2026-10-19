package rio.dan.mare.launcher;

import android.accessibilityservice.AccessibilityService;
import android.content.Intent;
import android.content.SharedPreferences;
import android.view.KeyEvent;
import android.view.accessibility.AccessibilityEvent;
import org.json.JSONObject;

/**
 * Remote buttons assigned in Settings: each opens its app or switches to its input, from anywhere on the TV, the way
 * its Home tile would. Every other key passes through untouched. Android only lets an accessibility service see keys
 * before the TV acts on them; this one asks for key events alone and reads nothing on the screen.
 */
public class RemoteButtons extends AccessibilityService {
    /** The launcher, while it waits for the button to assign: the next assignable press goes to it instead. */
    interface Listener { void pressed(int code, String name); }
    static volatile Listener listener;

    private SharedPreferences prefs;

    @Override protected void onServiceConnected() { prefs = getSharedPreferences("launcher", MODE_PRIVATE); }

    @Override protected boolean onKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        if (!assignable(code)) return false;
        boolean first = event.getAction() == KeyEvent.ACTION_DOWN && event.getRepeatCount() == 0;
        Listener waiting = listener;
        if (waiting != null) { if (first) { android.util.Log.i("MareRemote", "pressed " + code + " to assign"); waiting.pressed(code, name(code)); } return true; }
        String target = prefs == null ? null : assigned(prefs).optString(String.valueOf(code), null);
        if (target == null) return false;
        // the press, its repeats and its release are the button's: nothing else on the TV acts on them
        if (first) {
            android.util.Log.i("MareRemote", "button " + code + " opens " + target);
            Intent intent = Targets.intent(this, target);
            if (intent != null) try { startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); } catch (Exception ignored) {}
        }
        return true;
    }

    @Override public void onAccessibilityEvent(AccessibilityEvent event) {}
    @Override public void onInterrupt() {}

    /** The buttons assigned so far: key code to "app:<package>" or "input:<id>". */
    static JSONObject assigned(SharedPreferences prefs) {
        try { return new JSONObject(prefs.getString("buttons", "{}")); } catch (Exception e) { return new JSONObject(); }
    }

    /** Navigation, volume and power stay the TV's: they can't be assigned. */
    static boolean assignable(int code) {
        switch (code) {
            case KeyEvent.KEYCODE_DPAD_UP: case KeyEvent.KEYCODE_DPAD_DOWN: case KeyEvent.KEYCODE_DPAD_LEFT: case KeyEvent.KEYCODE_DPAD_RIGHT:
            case KeyEvent.KEYCODE_DPAD_CENTER: case KeyEvent.KEYCODE_ENTER: case KeyEvent.KEYCODE_NUMPAD_ENTER: case KeyEvent.KEYCODE_BACK:
            case KeyEvent.KEYCODE_HOME: case KeyEvent.KEYCODE_POWER: case KeyEvent.KEYCODE_TV_POWER: case KeyEvent.KEYCODE_SLEEP: case KeyEvent.KEYCODE_WAKEUP:
            case KeyEvent.KEYCODE_VOLUME_UP: case KeyEvent.KEYCODE_VOLUME_DOWN: case KeyEvent.KEYCODE_VOLUME_MUTE: case KeyEvent.KEYCODE_MUTE:
                return false;
            default:
                return code != KeyEvent.KEYCODE_UNKNOWN;
        }
    }

    /** "prog red" for a key Android names; a manufacturer's own key by its number, "button 4065". */
    static String name(int code) {
        String name = KeyEvent.keyCodeToString(code);
        return name.startsWith("KEYCODE_") ? name.substring(8).toLowerCase(java.util.Locale.ROOT).replace('_', ' ') : "button " + code;
    }
}
