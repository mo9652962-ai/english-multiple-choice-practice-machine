package com.moti.englishpractice;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(android.os.Bundle savedInstanceState) {
        registerPlugin(com.moti.englishpractice.SecureStoragePlugin.class);
        registerPlugin(com.moti.englishpractice.OpenApkPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
