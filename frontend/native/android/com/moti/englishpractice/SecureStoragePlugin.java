package com.moti.englishpractice;

import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import android.util.Log;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** SecureStoragePlugin: Android Keystore AES/GCM storage for provider keys. */
@CapacitorPlugin(name = "SecureStorage")
public class SecureStoragePlugin extends Plugin {

    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";
    private static final String KEY_ALIAS = "epm_secure_key";
    private static final int GCM_TAG_BITS = 128;
    private static final int IV_SIZE = 12;
    private static final String LOG_TAG = "EPM_ANDROID_SMOKE";

    private SecretKey getOrCreateKey() throws Exception {
        KeyStore keyStore = KeyStore.getInstance(ANDROID_KEYSTORE);
        keyStore.load(null);
        if (keyStore.containsAlias(KEY_ALIAS)) {
            return ((KeyStore.SecretKeyEntry) keyStore.getEntry(KEY_ALIAS, null)).getSecretKey();
        }
        KeyGenerator generator = KeyGenerator.getInstance(
                KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE);
        generator.init(new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build());
        return generator.generateKey();
    }

    private String encryptValue(String plaintext) throws Exception {
        SecretKey key = getOrCreateKey();
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key);
        byte[] cipherBytes = cipher.doFinal(plaintext.getBytes(StandardCharsets.UTF_8));
        byte[] iv = cipher.getIV();
        if (iv == null || iv.length != IV_SIZE) {
            throw new IllegalStateException("unexpected GCM IV size");
        }
        return Base64.encodeToString(iv, Base64.NO_WRAP) + ":"
                + Base64.encodeToString(cipherBytes, Base64.NO_WRAP);
    }

    private String decryptValue(String encoded) throws Exception {
        String[] parts = encoded.split(":", 2);
        if (parts.length != 2 || parts[0].isEmpty() || parts[1].isEmpty()) {
            throw new IllegalArgumentException("invalid encrypted value");
        }
        byte[] iv = Base64.decode(parts[0], Base64.NO_WRAP);
        byte[] cipherBytes = Base64.decode(parts[1], Base64.NO_WRAP);
        if (iv.length != IV_SIZE) {
            throw new IllegalArgumentException("invalid GCM IV size");
        }
        SecretKey key = getOrCreateKey();
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(GCM_TAG_BITS, iv));
        return new String(cipher.doFinal(cipherBytes), StandardCharsets.UTF_8);
    }

    @PluginMethod
    public void encrypt(PluginCall call) {
        try {
            String plaintext = call.getString("value");
            if (plaintext == null) {
                call.reject("value is required");
                return;
            }
            JSObject result = new JSObject();
            result.put("value", encryptValue(plaintext));
            call.resolve(result);
        } catch (Exception e) {
            call.reject("encrypt failed: " + e.getMessage());
        }
    }

    @PluginMethod
    public void decrypt(PluginCall call) {
        try {
            String encoded = call.getString("value");
            if (encoded == null || !encoded.contains(":")) {
                call.reject("invalid encrypted value");
                return;
            }
            JSObject result = new JSObject();
            result.put("value", decryptValue(encoded));
            call.resolve(result);
        } catch (Exception e) {
            call.reject("decrypt failed: " + e.getMessage());
        }
    }

    /** Debug smoke contract; it never returns key material. */
    @PluginMethod
    public void selfTest(PluginCall call) {
        try {
            String encrypted = encryptValue("epm-keystore-smoke");
            boolean roundTrip = "epm-keystore-smoke".equals(decryptValue(encrypted));
            if (!roundTrip) {
                call.reject("keystore round-trip mismatch");
                return;
            }
            JSObject result = new JSObject();
            result.put("round_trip", true);
            result.put("provider", ANDROID_KEYSTORE);
            Log.i(LOG_TAG, "keystore_round_trip=ok provider=" + ANDROID_KEYSTORE);
            call.resolve(result);
        } catch (Exception e) {
            call.reject("keystore self-test failed: " + e.getMessage());
        }
    }
}
