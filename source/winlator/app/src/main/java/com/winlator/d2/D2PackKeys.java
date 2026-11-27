package com.winlator.d2;

import android.app.Activity;
import com.winlator.core.AppUtils;
import android.app.AlertDialog;
import android.util.TypedValue;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

/**
 * The hotkeys the pack itself binds in Plugin\d2hackmap.cfg. Winlator users had to memorise
 * VK_Y / VK_D / VK_F ... and type them on a keyboard; here they are one tap each.
 */
public final class D2PackKeys {

    private static final int VK_0 = 0x30, VK_6 = 0x36, VK_7 = 0x37, VK_9 = 0x39;
    private static final int VK_D = 0x44, VK_E = 0x45, VK_F = 0x46, VK_G = 0x47, VK_J = 0x4A, VK_K = 0x4B,
        VK_N = 0x4E, VK_Y = 0x59, VK_F12 = 0x7B, VK_NUMPAD9 = 0x69;

    private static final String[] NAMES = {
        "显示物品 开/关", "隐藏垃圾物品", "查看装备属性", "一键开门", "一键回城", "一键鉴定全部",
        "药水进腰带", "开仓库(大箱子)", "开赫拉迪克方块", "自动拾取 开/关", "镶嵌保护 开/关",
        "重新载入配置", "一键退出游戏"
    };
    private static final int[] KEYS = {
        VK_Y, VK_N, VK_K, VK_J, VK_G, VK_E, VK_9, VK_D, VK_F, VK_6, VK_F12, VK_NUMPAD9, VK_7
    };
    private static final String[] HINTS = {
        "d2hackmap: Perm Show Items Toggle", "d2hackmap: Hidden Items Toggle", "d2hackmap: View Equipment Key",
        "d2hackmap: OpenDoorKey", "d2hackmap: Quick Back To Town Key", "d2hackmap: QuickIdentifyItemKey",
        "d2hackmap: Quick Potion To Belt Key", "d2hackmap: OpenStashKey", "d2hackmap: OpenCubeKey",
        "d2hackmap: Auto Pick Item Toggle", "d2hackmap: Socket Protect Toggle",
        "d2hackmap: Reload Config Key", "d2hackmap: Quick Exit Game Key"
    };

    private D2PackKeys() { }

    public static void show(Activity activity, D2TouchOverlay overlay) {
        float density = activity.getResources().getDisplayMetrics().density;
        int pad = Math.round(16 * density);

        LinearLayout list = new LinearLayout(activity);
        list.setOrientation(LinearLayout.VERTICAL);
        list.setPadding(pad, pad, pad, Math.round(8 * density));

        TextView title = new TextView(activity);
        title.setText("整合包快捷键");
        title.setTextSize(20);
        D2Style.heading(title);
        list.addView(title);

        TextView hint = new TextView(activity);
        hint.setText("这些是整合包 d2hackmap.cfg 里已经绑好的功能键，点一下等于在 Winlator 里按那个键。");
        hint.setTextSize(13);
        D2Style.hint(hint);
        hint.setPadding(0, Math.round(6 * density), 0, Math.round(6 * density));
        list.addView(hint);

        ScrollView scroll = new ScrollView(activity);
        scroll.setScrollbarFadingEnabled(false);
        scroll.addView(list);

        AlertDialog dialog = new AlertDialog.Builder(activity).setView(scroll).create();

        List<TextView> rows = new ArrayList<>();
        for (int i = 0; i < NAMES.length; i++) {
            final int vk = KEYS[i];
            TextView row = new TextView(activity);
            row.setText(NAMES[i]);
            row.setTextSize(17);
            D2Style.text(row);
            row.setGravity(Gravity.START);
            row.setPadding(0, Math.round(10 * density), 0, Math.round(10 * density));
            row.setOnClickListener((v) -> {
                overlay.tapKey(vk);
                dialog.dismiss();
            });
            list.addView(row);
            rows.add(row);
        }

        list.addView(note(activity, "经验获取、怪物等级/TC/血量、场景等级、跳过任务提示在 cfg 里默认已开（值为 1），不用按键。", density));
        list.addView(note(activity, "技能效果、符文之语、暗金、初始装备都来自整合包自己的 mpq，我们不覆盖。", density));

        D2PadFocus.all(list);
        dialog.setOnShowListener((d) -> AppUtils.hideSystemUI(activity));
        dialog.show();
    }

    private static TextView note(Activity activity, String text, float density) {
        TextView note = new TextView(activity);
        note.setText(text);
        note.setTextSize(TypedValue.COMPLEX_UNIT_SP, 12);
        D2Style.hint(note);
        note.setPadding(0, Math.round(8 * density), 0, 0);
        return note;
    }
}
