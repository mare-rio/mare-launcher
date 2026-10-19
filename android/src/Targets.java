package rio.dan.mare.launcher;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.tv.TvContract;
import android.media.tv.TvInputInfo;
import android.media.tv.TvInputManager;

/** What a tile or a remote button opens: an app's package ("app:<package>") or a TV input ("input:<id>"). */
final class Targets {
    private Targets() {}

    /** The intent that opens [target], or null when the app or input is not on this TV. */
    static Intent intent(Context context, String target) {
        if (target.startsWith("app:")) return app(context.getPackageManager(), target.substring(4));
        if (target.startsWith("input:")) return input(context, target.substring(6));
        return null;
    }

    static Intent app(PackageManager pm, String pkg) {
        Intent intent = pm.getLeanbackLaunchIntentForPackage(pkg);
        return intent != null ? intent : pm.getLaunchIntentForPackage(pkg);
    }

    /** A passthrough input (an HDMI port) opens as its channel item; a tuner as its channel list. */
    static Intent input(Context context, String id) {
        TvInputManager manager = (TvInputManager)context.getSystemService(Context.TV_INPUT_SERVICE);
        TvInputInfo input = manager == null ? null : manager.getTvInputInfo(id);
        if (input == null) return null;
        Intent intent = input.isPassthroughInput()
            ? new Intent(Intent.ACTION_VIEW).setDataAndType(TvContract.buildChannelUriForPassthroughInput(id), TvContract.Channels.CONTENT_ITEM_TYPE)
            : new Intent(Intent.ACTION_VIEW).setDataAndType(TvContract.buildChannelsUriForInput(id), TvContract.Channels.CONTENT_TYPE);
        return intent.resolveActivity(context.getPackageManager()) != null ? intent : null;
    }
}
