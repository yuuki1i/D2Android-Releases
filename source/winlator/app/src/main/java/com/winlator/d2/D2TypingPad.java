package com.winlator.d2;

import android.app.Dialog;
import android.content.Context;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.view.Gravity;
import android.view.View;
import android.widget.LinearLayout;
import android.widget.TextView;

import com.winlator.xserver.Keyboard;

import com.winlator.R;

/** A pad that types straight into the game. No Android keyboard involved, so nothing can
    swallow the input: every tap is one injected key press. */
public final class D2TypingPad {

    private D2TypingPad() {}


    public static void show(Context context, Keyboard keyboard) {
        Dialog dialog = new Dialog(context);
        dialog.requestWindowFeature(android.view.Window.FEATURE_NO_TITLE);
        float dp = context.getResources().getDisplayMetrics().density;

        LinearLayout root = new LinearLayout(context);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding((int) (10 * dp), (int) (8 * dp), (int) (10 * dp), (int) (8 * dp));
        root.setBackgroundColor(0xEE101010);

        TextView title = new TextView(context);
        title.setText(context.getString(R.string.menu_text));
        title.setTextColor(0xFFE8D9A0);
        title.setTextSize(14);
        title.setGravity(Gravity.CENTER);
        root.addView(title);

        String[] rows = {"1234567890", "QWERTYUIOP", "ASDFGHJKL-", "ZXCVBNM,."};
        for (String row : rows) root.addView(row(context, keyboard, row.split(""), dialog, dp));

        LinearLayout bottom = new LinearLayout(context);
        bottom.setOrientation(LinearLayout.HORIZONTAL);
        bottom.setGravity(Gravity.CENTER);
        bottom.addView(key(context, keyboard, "空格", " ", dp));
        bottom.addView(key(context, keyboard, "删除", "\b", dp));
        TextView done = key(context, keyboard, "完成", null, dp);
        done.setOnClickListener((v) -> dialog.dismiss());
        bottom.addView(done);
        root.addView(bottom);

        dialog.setContentView(root);
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            dialog.getWindow().setGravity(Gravity.BOTTOM);
        }
        dialog.show();
    }


    private static LinearLayout row(Context context, Keyboard keyboard, String[] keys, Dialog dialog, float dp) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        for (String k : keys) if(!k.isEmpty()) row.addView(key(context, keyboard, k, k, dp));
        return row;
    }


    private static TextView key(Context context, Keyboard keyboard, String label, String send, float dp) {
        TextView v = new TextView(context);
        v.setText(label);
        v.setTextColor(0xFFEDEDED);
        v.setTextSize(15);
        v.setGravity(Gravity.CENTER);
        int w = (int) ((send != null && send.length() > 1 ? 54 : 30) * dp);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(w, (int) (38 * dp));
        p.setMargins((int) (2 * dp), (int) (2 * dp), (int) (2 * dp), (int) (2 * dp));
        v.setLayoutParams(p);
        android.graphics.drawable.GradientDrawable bg = new android.graphics.drawable.GradientDrawable();
        bg.setColor(0xFF2B2B2B);
        bg.setCornerRadius(6 * dp);
        bg.setStroke((int) dp, 0x55FFFFFF);
        v.setBackground(bg);
        if (send != null) {
            v.setOnClickListener((view) -> {
                if ("\b".equals(send)) keyboard.backspace();
                else keyboard.typeText(send);
            });
        }
        return v;
    }
}
