package com.viper.sdk;

import android.app.Activity;
import android.os.Bundle;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private static final String DEFAULT_SDK_URL = "http://127.0.0.1:18181";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(0xff0d1117);

        TextView header = new TextView(this);
        header.setText("VIPER SDK APK SHELL");
        header.setTextColor(0xfff0f6fc);
        header.setTextSize(14);
        header.setPadding(14, 12, 14, 10);
        header.setBackgroundColor(0xff161b22);
        header.setTypeface(android.graphics.Typeface.MONOSPACE);

        WebView webView = new WebView(this);
        webView.setBackgroundColor(0xff0d1117);
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);

        root.addView(header, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        ));
        root.addView(webView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                0,
                1
        ));
        setContentView(root);

        webView.loadUrl(DEFAULT_SDK_URL);
    }
}
