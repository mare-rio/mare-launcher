package rio.dan.mare.launcher;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ApplicationInfo;
import android.content.pm.ResolveInfo;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.*;
import android.widget.Toast;
import java.io.ByteArrayInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.*;

/** A local Maré surface. Its only bridge actions are catalog-validated Android intents. */
public class LauncherActivity extends Activity {
    private static final String ORIGIN = "https://mare-launcher.local/";
    private WebView web;
    private SharedPreferences prefs;
    private volatile Set<String> packages = Collections.emptySet();
    private volatile Set<String> inputs = Collections.emptySet();
    private volatile String catalog = "{}";
    private boolean ready = false;
    private int rendererRestarts = 0;
    private TvInputManager inputManager;
    private final TvInputManager.TvInputCallback inputCallback = new TvInputManager.TvInputCallback() {
        @Override public void onInputStateChanged(String inputId, int state) { refreshCatalog(); }
        @Override public void onInputAdded(String inputId) { refreshCatalog(); }
        @Override public void onInputRemoved(String inputId) { refreshCatalog(); }
        @Override public void onInputUpdated(String inputId) { refreshCatalog(); }
    };
    private void refreshCatalog() {
        rebuildCatalog();
        if (ready) web.evaluateJavascript("window.refreshTV && window.refreshTV()", null);
    }
    private void migrateLayout() {
        if (prefs.contains("layoutVersion")) return;
        SharedPreferences.Editor editor = prefs.edit();
        try {
            android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            // 0.1 displayed these defaults without storing them. Preserve that home on upgrade;
            // a new installation starts with the handoff's Choose your favourites row.
            if (!prefs.contains("favorites") && info.lastUpdateTime > info.firstInstallTime) {
                JSONArray defaults = new JSONArray();
                for (String pkg : new String[]{"org.smarttube.stable", "org.jellyfin.androidtv", "com.stremio.one", "com.spotify.tv.android", "com.formulaone.production", "com.apple.atve.androidtv.appletv", "com.disney.disneyplus"}) {
                    if (packages.contains(pkg)) defaults.put(pkg);
                }
                editor.putString("favorites", defaults.toString());
            }
        } catch (PackageManager.NameNotFoundException ignored) {}
        editor.putInt("layoutVersion", 2).apply();
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        prefs = getSharedPreferences("launcher", MODE_PRIVATE);
        rebuildCatalog();
        migrateLayout();
        inputManager = (TvInputManager)getSystemService(TV_INPUT_SERVICE);
        if (inputManager != null) inputManager.registerCallback(inputCallback, new android.os.Handler(getMainLooper()));
        getWindow().getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_FULLSCREEN | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
        if (android.os.Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(android.window.OnBackInvokedDispatcher.PRIORITY_DEFAULT, () -> {
                if (ready && web != null) remote("back");
                else finish();
            });
        }
        createWebView();
    }

    private void createWebView() {
        ready = false;
        web = new WebView(this);
        web.setBackgroundColor(0xff070f0e);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setSupportZoom(false);
        settings.setTextZoom(100);
        settings.setMediaPlaybackRequiresUserGesture(true);
        WebView.setWebContentsDebuggingEnabled((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0);
        web.addJavascriptInterface(new Bridge(), "TV");
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onConsoleMessage(ConsoleMessage message) {
                android.util.Log.d("MareLauncher", message.message());
                return true;
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest request) { return true; }
            @Override public WebResourceResponse shouldInterceptRequest(WebView v, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (!"https".equals(uri.getScheme()) || !"mare-launcher.local".equals(uri.getHost())) return denied();
                String path = uri.getPath();
                if (path == null || path.contains("..") || path.indexOf('\\') >= 0) return denied();
                if (path.equals("/")) path = "/index.html";
                try {
                    String mime = path.endsWith(".html") ? "text/html" : path.endsWith(".js") ? "application/javascript" : path.endsWith(".css") ? "text/css" : path.endsWith(".svg") ? "image/svg+xml" : path.endsWith(".ttf") ? "font/ttf" : "application/octet-stream";
                    return new WebResourceResponse(mime, "UTF-8", getAssets().open("web" + path));
                } catch (Exception e) { return denied(); }
            }
            @Override public void onPageFinished(WebView v, String url) { ready = url.equals(ORIGIN); }
            @Override public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
                ready = false;
                view.removeJavascriptInterface("TV");
                if (view.getParent() instanceof android.view.ViewGroup) ((android.view.ViewGroup)view.getParent()).removeView(view);
                view.destroy(); web = null;
                if (!detail.didCrash() || ++rendererRestarts <= 2) {
                    if (hasWindowFocus() && !isFinishing()) getWindow().getDecorView().post(() -> createWebView());
                }
                else {
                    android.widget.Button settings = new android.widget.Button(LauncherActivity.this);
                    settings.setText("Maré could not start. Open TV settings to update Android System WebView.");
                    settings.setOnClickListener(v -> open(new Intent(Settings.ACTION_SETTINGS)));
                    setContentView(settings); settings.requestFocus();
                }
                return true;
            }
        });
        setContentView(web);
        web.loadUrl(ORIGIN);
        web.requestFocus();
    }

    private WebResourceResponse denied() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", Collections.emptyMap(), new ByteArrayInputStream(new byte[0]));
    }

    private synchronized void rebuildCatalog() {
        try {
            PackageManager pm = getPackageManager();
            TreeMap<String, ResolveInfo> apps = new TreeMap<>();
            for (String category : new String[]{Intent.CATEGORY_LEANBACK_LAUNCHER, Intent.CATEGORY_LAUNCHER}) {
                Intent query = new Intent(Intent.ACTION_MAIN).addCategory(category);
                for (ResolveInfo info : pm.queryIntentActivities(query, 0)) {
                    if (info.activityInfo.exported && info.activityInfo.enabled && info.activityInfo.applicationInfo.enabled) apps.put(info.activityInfo.packageName, info);
                }
            }
            JSONArray items = new JSONArray(); Set<String> newPackages = new HashSet<>();
            for (Map.Entry<String, ResolveInfo> entry : apps.entrySet()) {
                String pkg = entry.getKey();
                if (pkg.equals(getPackageName())) continue;
                newPackages.add(pkg);
                JSONObject item = new JSONObject().put("package", pkg).put("name", entry.getValue().loadLabel(pm).toString());
                item.put("tv", pm.getLeanbackLaunchIntentForPackage(pkg) != null);
                items.put(item);
            }
            JSONArray ports = new JSONArray(); Set<String> newInputs = new HashSet<>();
            String inputError = "";
            try {
                TvInputManager manager = (TvInputManager)getSystemService(TV_INPUT_SERVICE);
                for (TvInputInfo input : manager == null ? Collections.<TvInputInfo>emptyList() : manager.getTvInputList()) {
                    if (input.getType() != TvInputInfo.TYPE_HDMI && input.getType() != TvInputInfo.TYPE_TUNER && input.getType() != TvInputInfo.TYPE_COMPOSITE) continue;
                    // Streaming apps also register virtual tuners. They belong in Apps, not physical Inputs.
                    if (input.getType() == TvInputInfo.TYPE_TUNER && (input.getServiceInfo().applicationInfo.flags & ApplicationInfo.FLAG_SYSTEM) == 0) continue;
                    newInputs.add(input.getId());
                    CharSequence label = input.loadCustomLabel(this);
                    if (label == null || label.length() == 0) label = input.loadLabel(this);
                    ports.put(new JSONObject().put("id", input.getId()).put("name", String.valueOf(label)).put("label", String.valueOf(input.loadLabel(this))).put("type", input.getType()).put("state", manager.getInputState(input.getId())).put("passthrough", input.isPassthroughInput()));
                }
            } catch (Exception e) { inputError = "TV inputs are not available through Android."; }
            JSONObject data = new JSONObject().put("apps", items).put("inputs", ports).put("inputError", inputError);
            packages = Collections.unmodifiableSet(newPackages);
            inputs = Collections.unmodifiableSet(newInputs);
            catalog = data.toString();
            try (FileOutputStream out = openFileOutput("catalog.json", MODE_PRIVATE)) { out.write(catalog.getBytes(StandardCharsets.UTF_8)); }
        } catch (Exception e) { android.util.Log.e("MareLauncher", "Catalog", e); }
    }

    private void open(Intent intent) {
        try { startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); }
        catch (Exception e) { Toast.makeText(this, "Unable to open. Please use TV settings.", Toast.LENGTH_LONG).show(); }
    }

    private class Bridge {
        @JavascriptInterface public String catalog() { return catalog; }
        @JavascriptInterface public String version() {
            try { return getPackageManager().getPackageInfo(getPackageName(), 0).versionName; }
            catch (PackageManager.NameNotFoundException e) { return "unknown"; }
        }
        @JavascriptInterface public String preferences() {
            try {
                return new JSONObject().put("theme", prefs.getString("theme", "night")).put("initialized", prefs.contains("favorites")).put("favorites", new JSONArray(prefs.getString("favorites", "[]"))).put("motion", prefs.getBoolean("motion", true)).put("systemReduced", !android.animation.ValueAnimator.areAnimatorsEnabled()).toString();
            } catch (Exception e) { return "{}"; }
        }
        @JavascriptInterface public void save(String key, String value) {
            if (key.equals("theme") && (value.equals("day") || value.equals("night"))) prefs.edit().putString(key, value).apply();
            if (key.equals("motion")) prefs.edit().putBoolean(key, value.equals("true")).apply();
            if (key.equals("favorites")) {
                try {
                    JSONArray proposed = new JSONArray(value), valid = new JSONArray(); Set<String> unique = new HashSet<>();
                    for (int i=0; i<proposed.length() && valid.length()<12; i++) {
                        String pkg = proposed.getString(i);
                        if (packages.contains(pkg) && unique.add(pkg)) valid.put(pkg);
                    }
                    prefs.edit().putString(key, valid.toString()).apply();
                } catch (Exception ignored) {}
            }
        }
        @JavascriptInterface public void launch(String pkg) {
            if (!packages.contains(pkg)) return;
            runOnUiThread(() -> {
                PackageManager pm = getPackageManager();
                Intent intent = pm.getLeanbackLaunchIntentForPackage(pkg);
                if (intent == null) intent = pm.getLaunchIntentForPackage(pkg);
                if (intent != null) open(intent);
            });
        }
        @JavascriptInterface public void appInfo(String pkg) {
            if (packages.contains(pkg)) runOnUiThread(() -> open(new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:" + pkg))));
        }
        @JavascriptInterface public void input(String id) {
            if (!inputs.contains(id)) return;
            runOnUiThread(() -> {
                TvInputManager manager = (TvInputManager)getSystemService(TV_INPUT_SERVICE);
                TvInputInfo input = manager == null ? null : manager.getTvInputInfo(id);
                if (input == null) return;
                Intent intent = input.isPassthroughInput()
                    ? new Intent(Intent.ACTION_VIEW).setDataAndType(TvContract.buildChannelUriForPassthroughInput(id), TvContract.Channels.CONTENT_ITEM_TYPE)
                    : new Intent(Intent.ACTION_VIEW).setDataAndType(TvContract.buildChannelsUriForInput(id), TvContract.Channels.CONTENT_TYPE);
                if (intent.resolveActivity(getPackageManager()) != null) open(intent);
                else Toast.makeText(LauncherActivity.this, "Use your TV remote’s Input or Live TV button.", Toast.LENGTH_LONG).show();
            });
        }
        @JavascriptInterface public void settings(String page) {
            runOnUiThread(() -> {
                String action = page.equals("network") ? Settings.ACTION_WIFI_SETTINGS : page.equals("bluetooth") ? Settings.ACTION_BLUETOOTH_SETTINGS : Settings.ACTION_SETTINGS;
                Intent intent = new Intent(action);
                if (intent.resolveActivity(getPackageManager()) == null) intent = new Intent(Settings.ACTION_SETTINGS);
                open(intent);
            });
        }
        @JavascriptInterface public String network() {
            ConnectivityManager manager = (ConnectivityManager)getSystemService(CONNECTIVITY_SERVICE);
            NetworkCapabilities caps = manager.getNetworkCapabilities(manager.getActiveNetwork());
            if (caps == null) return "No network";
            String label = caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) ? "Ethernet" : caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ? "Wi-Fi" : "Network";
            return label + (caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED) ? " connected" : " · local network");
        }
        @JavascriptInterface public void exit() { runOnUiThread(() -> finish()); }
    }

    private void remote(String key) {
        web.evaluateJavascript("window.remoteKey && window.remoteKey(" + JSONObject.quote(key) + ")", null);
    }
    @Override public boolean dispatchKeyEvent(KeyEvent event) {
        int code = event.getKeyCode();
        boolean direction = code >= KeyEvent.KEYCODE_DPAD_UP && code <= KeyEvent.KEYCODE_DPAD_RIGHT;
        boolean enter = code == KeyEvent.KEYCODE_DPAD_CENTER || code == KeyEvent.KEYCODE_ENTER;
        // Modern TV firmware can deliver both the key and the Back callback.
        // Let the dispatcher own Back on API 33+, so one press closes one layer.
        boolean legacyBack = code == KeyEvent.KEYCODE_BACK && android.os.Build.VERSION.SDK_INT < 33;
        if (ready && (direction || enter || legacyBack || code == KeyEvent.KEYCODE_MENU || code == KeyEvent.KEYCODE_TV_INPUT)) {
            if (event.isCanceled()) web.evaluateJavascript("window.cancelRemoteHold && window.cancelRemoteHold()", null);
            else if (enter && event.getAction() == KeyEvent.ACTION_UP) remote("enter-up");
            else if (event.getAction() == KeyEvent.ACTION_DOWN && (event.getRepeatCount() == 0 || direction)) {
                remote(code == 19 ? "up" : code == 20 ? "down" : code == 21 ? "left" : code == 22 ? "right" : code == 4 ? "back" : code == 82 ? "menu" : code == 178 ? "source" : "enter");
            }
            return true;
        }
        return super.dispatchKeyEvent(event);
    }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        if (ready) web.evaluateJavascript("window.launcherHome && window.launcherHome()", null);
    }
    @Override protected void onResume() {
        super.onResume();
        if (web == null && rendererRestarts <= 2) createWebView();
        if (web != null) {
            web.onResume(); web.resumeTimers();
            if (ready) {
                rebuildCatalog();
                web.evaluateJavascript("window.refreshTV && window.refreshTV(); window.launcherHome && window.launcherHome()", null);
            }
        }
    }
    @Override protected void onPause() {
        if (web != null) {
            web.evaluateJavascript("window.cancelRemoteHold && window.cancelRemoteHold()", null);
            web.onPause(); web.pauseTimers();
        }
        super.onPause();
    }
    @Override public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (!hasFocus && ready && web != null) web.evaluateJavascript("window.cancelRemoteHold && window.cancelRemoteHold()", null);
    }
    @Override protected void onDestroy() { if (inputManager != null) inputManager.unregisterCallback(inputCallback); ready = false; if (web != null) { web.removeJavascriptInterface("TV"); web.destroy(); } super.onDestroy(); }
}
