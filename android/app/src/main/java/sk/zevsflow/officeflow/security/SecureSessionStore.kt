package sk.zevsflow.officeflow.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import java.io.DataInputStream
import java.io.DataOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import sk.zevsflow.officeflow.data.SessionCredentialStore
import sk.zevsflow.officeflow.data.SessionCredentials

class SecureSessionStore(
    context: Context,
    private val json: Json = Json { ignoreUnknownKeys = false; explicitNulls = false },
) : SessionCredentialStore {
    private val credentialFile = File(context.noBackupFilesDir, FILE_NAME)
    private val mutex = Mutex()

    override suspend fun load(): SessionCredentials? = mutex.withLock {
        withContext(Dispatchers.IO) {
            if (!credentialFile.exists()) return@withContext null
            try {
                DataInputStream(FileInputStream(credentialFile)).use { input ->
                    require(input.readUnsignedByte() == FORMAT_VERSION)
                    val ivLength = input.readUnsignedByte()
                    require(ivLength in 12..16)
                    val iv = ByteArray(ivLength).also(input::readFully)
                    val ciphertextLength = input.readInt()
                    require(ciphertextLength in 16..MAX_CIPHERTEXT_BYTES)
                    val ciphertext = ByteArray(ciphertextLength).also(input::readFully)
                    require(input.read() == -1)
                    val cipher = Cipher.getInstance(TRANSFORMATION)
                    cipher.init(Cipher.DECRYPT_MODE, existingKey(), GCMParameterSpec(128, iv))
                    val plaintext = cipher.doFinal(ciphertext).decodeToString()
                    json.decodeFromString(SessionCredentials.serializer(), plaintext)
                }
            } catch (_: Exception) {
                clearMaterial(deleteKey = true)
                null
            }
        }
    }

    override suspend fun replace(credentials: SessionCredentials) {
        mutex.withLock {
            withContext(Dispatchers.IO) {
                val plaintext = json.encodeToString(credentials).encodeToByteArray()
                require(plaintext.size <= MAX_PLAINTEXT_BYTES)
                val cipher = Cipher.getInstance(TRANSFORMATION)
                cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
                val ciphertext = cipher.doFinal(plaintext)
                val temporary = File(credentialFile.parentFile, "$FILE_NAME.tmp")
                FileOutputStream(temporary).use { fileOutput ->
                    DataOutputStream(fileOutput).use { output ->
                        output.writeByte(FORMAT_VERSION)
                        output.writeByte(cipher.iv.size)
                        output.write(cipher.iv)
                        output.writeInt(ciphertext.size)
                        output.write(ciphertext)
                        output.flush()
                        fileOutput.fd.sync()
                    }
                }
                try {
                    Files.move(
                        temporary.toPath(),
                        credentialFile.toPath(),
                        StandardCopyOption.ATOMIC_MOVE,
                        StandardCopyOption.REPLACE_EXISTING,
                    )
                } catch (exc: Exception) {
                    temporary.delete()
                    throw IllegalStateException("secure_session_replace_failed", exc)
                }
            }
        }
    }

    override suspend fun clear() = mutex.withLock {
        withContext(Dispatchers.IO) { clearMaterial(deleteKey = true) }
    }

    private fun clearMaterial(deleteKey: Boolean) {
        credentialFile.delete()
        File(credentialFile.parentFile, "$FILE_NAME.tmp").delete()
        if (deleteKey) {
            val keyStore = keyStore()
            if (keyStore.containsAlias(KEY_ALIAS)) keyStore.deleteEntry(KEY_ALIAS)
        }
    }

    private fun existingKey(): SecretKey {
        val key = keyStore().getKey(KEY_ALIAS, null)
        return key as? SecretKey ?: error("secure_session_key_missing")
    }

    private fun getOrCreateKey(): SecretKey = try {
        existingKey()
    } catch (_: Exception) {
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        generator.generateKey()
    }

    private fun keyStore(): KeyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }

    companion object {
        private const val ANDROID_KEYSTORE = "AndroidKeyStore"
        private const val KEY_ALIAS = "officeflow.stageb.session.aes"
        private const val TRANSFORMATION = "AES/GCM/NoPadding"
        private const val FILE_NAME = "officeflow_session.enc"
        private const val FORMAT_VERSION = 1
        private const val MAX_PLAINTEXT_BYTES = 4 * 1024
        private const val MAX_CIPHERTEXT_BYTES = 8 * 1024
    }
}
