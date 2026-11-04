package com.pythonnative.plugins.biometrics

import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.pythonnative.generated.BiometricsImplementation
import com.pythonnative.generated.BiometricsModuleAdapter
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry

/** Registers `Biometrics`. */
object BiometricsPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { BiometricsModuleAdapter(BiometricsModule()) }
    }
}

/** `Biometrics.is_available()` (sync bool) and `authenticate(reason)` (async bool via `BiometricPrompt`). */
class BiometricsModule : BiometricsImplementation {
    override fun is_available(): Boolean = try {
        BiometricManager.from(PNBridge.context()).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS
    } catch (_: Exception) { false }

    override fun authenticate(reason: String, completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        val activity = PNBridge.activity() as? FragmentActivity ?: run { completion(Result.success(false)); return null }
        if (!is_available()) { completion(Result.success(false)); return null }
        return try {
            val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), object : BiometricPrompt.AuthenticationCallback() {
                override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = completion(Result.success(true))
                override fun onAuthenticationError(errorCode: Int, errString: CharSequence) = completion(Result.success(false))
                override fun onAuthenticationFailed() {}
            })
            val info = BiometricPrompt.PromptInfo.Builder().setTitle(reason).setNegativeButtonText("Cancel")
                .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_WEAK).build()
            prompt.authenticate(info)
            val cancel: () -> Unit = { prompt.cancelAuthentication() }
            cancel
        } catch (error: Exception) { completion(Result.failure(error)); null }
    }
}
