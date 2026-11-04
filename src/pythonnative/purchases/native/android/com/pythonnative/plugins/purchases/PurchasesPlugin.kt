package com.pythonnative.plugins.purchases

import android.app.Activity
import android.util.Log
import com.android.billingclient.api.AcknowledgePurchaseParams
import com.android.billingclient.api.BillingClient
import com.android.billingclient.api.BillingClientStateListener
import com.android.billingclient.api.BillingFlowParams
import com.android.billingclient.api.BillingResult
import com.android.billingclient.api.ConsumeParams
import com.android.billingclient.api.PendingPurchasesParams
import com.android.billingclient.api.ProductDetails
import com.android.billingclient.api.Purchase
import com.android.billingclient.api.PurchasesUpdatedListener
import com.android.billingclient.api.QueryProductDetailsParams
import com.android.billingclient.api.QueryPurchasesParams
import com.pythonnative.generated.PNJSONValue
import com.pythonnative.generated.PNValues
import com.pythonnative.generated.PurchasesImplementation
import com.pythonnative.generated.PurchasesModuleAdapter
import com.pythonnative.runtime.PNBridge
import com.pythonnative.runtime.bridge.MainThread
import com.pythonnative.runtime.bridge.PNPlugin
import com.pythonnative.runtime.bridge.PNRegistry
import com.pythonnative.runtime.modules.ModuleEvents
import com.pythonnative.runtime.modules.PNLifecycleHook
import com.pythonnative.runtime.modules.PNModuleError
import java.math.BigDecimal

private const val MAX_RECONNECTS = 3

private typealias Wire = Map<String, PNJSONValue>

/** Registers `Purchases`. Purchases made outside the app show up when the user comes back. */
object PurchasesPlugin : PNPlugin {
    override fun register(registry: PNRegistry) {
        registry.registerModule { PurchasesModuleAdapter(PurchasesModule()) }
        registry.registerLifecycleHook(object : PNLifecycleHook {
            override fun onActivityResumed(activity: Activity) = PNStore.refresh()
        })
    }
}

/** `Purchases`, through Google Play Billing. Every callback settles on the main thread, in [PNStore]. */
class PurchasesModule : PurchasesImplementation {
    override fun is_available(completion: (Result<Boolean>) -> Unit): (() -> Unit)? {
        PNStore.connected { client -> completion(Result.success(client.isSuccess)) }
        return null
    }

    override fun products(ids: List<String>, completion: (Result<List<Wire>>) -> Unit): (() -> Unit)? {
        PNStore.products(ids) { found -> completion(found.map { details -> details.map(PNStore::wire) }) }
        return null
    }

    override fun purchase(product_id: String, completion: (Result<Wire>) -> Unit): (() -> Unit)? {
        PNStore.purchase(product_id, completion)
        return null
    }

    override fun restore(completion: (Result<List<Wire>>) -> Unit): (() -> Unit)? {
        PNStore.owned { found ->
            completion(found.map { list -> list.filter { it.purchaseState == Purchase.PurchaseState.PURCHASED }.map(PNStore::wire) })
        }
        return null
    }

    override fun finish(consume: Boolean, id: String, token: String, completion: (Result<Unit>) -> Unit): (() -> Unit)? {
        PNStore.finish(token, consume, completion)
        return null
    }

    override fun listen() = PNStore.subscribe()
}

private fun billingError(result: BillingResult, code: String) = PNModuleError(
    result.debugMessage.ifEmpty { "Play Billing answered ${result.responseCode}" }, code
)

/** The one billing connection, and its retry. All state here belongs to the main thread. */
private object PNStore : PurchasesUpdatedListener, BillingClientStateListener {
    private class Active(val productId: String, val completion: (Result<Wire>) -> Unit)

    private var client: BillingClient? = null
    private val waiting = ArrayList<(Result<BillingClient>) -> Unit>()
    private var connecting = false
    private var reconnects = 0
    private val catalog = HashMap<String, ProductDetails>()
    private val acknowledged = HashSet<String>()
    private var active: Active? = null
    private var subscribed = false
    private val announced = HashSet<String>()
    private val held = ArrayList<Wire>()

    // ------------------------------------------------------------------
    // Connection
    // ------------------------------------------------------------------

    fun connected(done: (Result<BillingClient>) -> Unit) = MainThread.runOnMain {
        val current = client
        if (current != null && current.isReady) {
            done(Result.success(current))
        } else {
            waiting.add(done)
            if (!connecting) connect()
        }
    }

    private fun connect() {
        connecting = true
        val current = client ?: BillingClient.newBuilder(PNBridge.context().applicationContext)
            .setListener(this)
            .enablePendingPurchases(PendingPurchasesParams.newBuilder().enableOneTimeProducts().build())
            .build()
            .also { client = it }
        current.startConnection(this)
    }

    override fun onBillingSetupFinished(result: BillingResult) = MainThread.runOnMain {
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> {
                connecting = false
                reconnects = 0
                settle(Result.success(client!!))
            }
            BillingClient.BillingResponseCode.SERVICE_DISCONNECTED,
            BillingClient.BillingResponseCode.SERVICE_UNAVAILABLE,
            BillingClient.BillingResponseCode.NETWORK_ERROR,
            BillingClient.BillingResponseCode.ERROR -> reconnect(billingError(result, "unavailable"))
            else -> {
                // Not something a retry fixes: no Play Store, or an unsupported device.
                connecting = false
                settle(Result.failure(billingError(result, "unavailable")))
            }
        }
    }

    override fun onBillingServiceDisconnected() = MainThread.runOnMain {
        if (waiting.isEmpty()) connecting = false
        else reconnect(PNModuleError("The connection to Google Play was lost", "unavailable"))
    }

    private fun reconnect(failure: PNModuleError) {
        if (reconnects >= MAX_RECONNECTS) {
            connecting = false
            reconnects = 0
            settle(Result.failure(failure))
            return
        }
        reconnects += 1
        MainThread.postDelayed(Runnable { connect() }, 500L shl reconnects)
    }

    private fun settle(result: Result<BillingClient>) {
        val callers = ArrayList(waiting)
        waiting.clear()
        callers.forEach { it(result) }
    }

    /** Run `action` with a ready client, sending a failed connection to `failed`. */
    private fun <T> withClient(failed: (Result<T>) -> Unit, action: (BillingClient) -> Unit) = connected { connection ->
        connection.fold(action) { failed(Result.failure(it)) }
    }

    // ------------------------------------------------------------------
    // Products
    // ------------------------------------------------------------------

    fun products(ids: List<String>, done: (Result<List<ProductDetails>>) -> Unit) {
        if (ids.isEmpty()) {
            done(Result.success(emptyList()))
            return
        }
        withClient(done) { current ->
            // One request can't mix product types, and an id doesn't say which it is.
            query(current, ids, BillingClient.ProductType.INAPP) { inApp ->
                inApp.fold({ oneTime ->
                    query(current, ids, BillingClient.ProductType.SUBS) { subscriptions ->
                        done(subscriptions.map { oneTime + it })
                    }
                }, { done(Result.failure(it)) })
            }
        }
    }

    private fun query(current: BillingClient, ids: List<String>, type: String, done: (Result<List<ProductDetails>>) -> Unit) {
        val products = ids.map { QueryProductDetailsParams.Product.newBuilder().setProductId(it).setProductType(type).build() }
        val params = QueryProductDetailsParams.newBuilder().setProductList(products).build()
        current.queryProductDetailsAsync(params) { result, found ->
            MainThread.runOnMain {
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    found.productDetailsList.forEach { catalog[it.productId] = it }
                    done(Result.success(found.productDetailsList))
                } else {
                    done(Result.failure(billingError(result, "store_error")))
                }
            }
        }
    }

    fun wire(details: ProductDetails): Wire {
        val oneTime = details.oneTimePurchaseOfferDetails
        // A subscription's first phases can be a free trial. The last one is what it costs.
        val recurring = details.subscriptionOfferDetails?.firstOrNull()?.pricingPhases?.pricingPhaseList?.lastOrNull()
        val micros = oneTime?.priceAmountMicros ?: recurring?.priceAmountMicros ?: 0L
        return mapOf(
            "id" to PNJSONValue(details.productId),
            "title" to PNJSONValue(details.name),
            "description" to PNJSONValue(details.description),
            "price" to PNJSONValue(BigDecimal(micros).movePointLeft(6).stripTrailingZeros().toPlainString()),
            "currency" to PNJSONValue(oneTime?.priceCurrencyCode ?: recurring?.priceCurrencyCode ?: ""),
            "display_price" to PNJSONValue(oneTime?.formattedPrice ?: recurring?.formattedPrice ?: ""),
            "kind" to PNJSONValue(if (details.productType == BillingClient.ProductType.SUBS) "subscription" else "one_time"),
        )
    }

    fun wire(purchase: Purchase): Wire = mapOf(
        // Play has no order id until a pending purchase completes.
        "id" to PNJSONValue(purchase.orderId ?: purchase.purchaseToken),
        "product_id" to PNJSONValue(purchase.products.firstOrNull() ?: ""),
        "purchase_date" to PNJSONValue(purchase.purchaseTime / 1000.0),
        "token" to PNJSONValue(purchase.purchaseToken),
        "verified" to PNJSONValue(false),
        "revoked" to PNJSONValue(false),
    )

    // ------------------------------------------------------------------
    // Purchasing
    // ------------------------------------------------------------------

    fun purchase(productId: String, done: (Result<Wire>) -> Unit) = MainThread.runOnMain {
        if (active != null) {
            done(Result.failure(PNModuleError("Another purchase is in progress", "purchase_failed")))
            return@runOnMain
        }
        val known = catalog[productId]
        if (known != null) {
            withClient(done) { launch(it, known, done) }
        } else {
            products(listOf(productId)) { found ->
                found.fold({ list ->
                    val details = list.firstOrNull()
                    if (details == null) done(Result.failure(PNModuleError("Google Play doesn't know the product \"$productId\"", "unknown_product")))
                    else withClient(done) { launch(it, details, done) }
                }, { done(Result.failure(it)) })
            }
        }
    }

    private fun launch(current: BillingClient, details: ProductDetails, done: (Result<Wire>) -> Unit) {
        val activity = PNBridge.activity()
        if (activity == null) {
            done(Result.failure(PNModuleError("A purchase needs a visible screen", "purchase_failed")))
            return
        }
        val product = BillingFlowParams.ProductDetailsParams.newBuilder().setProductDetails(details)
        details.subscriptionOfferDetails?.firstOrNull()?.let { product.setOfferToken(it.offerToken) }
        val params = BillingFlowParams.newBuilder().setProductDetailsParamsList(listOf(product.build())).build()
        active = Active(details.productId, done)
        val launched = current.launchBillingFlow(activity, params)
        if (launched.responseCode != BillingClient.BillingResponseCode.OK) {
            active = null
            done(Result.failure(billingError(launched, "purchase_failed")))
        }
    }

    override fun onPurchasesUpdated(result: BillingResult, purchases: MutableList<Purchase>?) = MainThread.runOnMain {
        val current = active
        when (result.responseCode) {
            BillingClient.BillingResponseCode.OK -> {
                for (purchase in purchases.orEmpty()) {
                    if (current != null && current.productId in purchase.products) {
                        active = null
                        current.completion(Result.success(outcome(purchase)))
                    } else {
                        announce(purchase)
                    }
                }
            }
            BillingClient.BillingResponseCode.USER_CANCELED -> {
                active = null
                current?.completion?.invoke(Result.success(mapOf("status" to PNJSONValue("cancelled"))))
            }
            BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED -> {
                active = null
                if (current != null) completeOwned(current)
            }
            else -> {
                active = null
                current?.completion?.invoke(Result.failure(billingError(result, "purchase_failed")))
            }
        }
    }

    private fun outcome(purchase: Purchase): Wire = if (purchase.purchaseState == Purchase.PurchaseState.PURCHASED) {
        announced.add(purchase.purchaseToken)
        mapOf("status" to PNJSONValue("purchased"), "transaction" to PNJSONValue(PNValues.encode(wire(purchase))))
    } else {
        mapOf("status" to PNJSONValue("pending"))
    }

    /** Play refuses to sell what the user owns. Like StoreKit, answer with what they already have. */
    private fun completeOwned(current: Active) = owned { found ->
        current.completion(found.mapCatching { list ->
            outcome(list.firstOrNull { current.productId in it.products }
                ?: throw PNModuleError("Google Play says \"${current.productId}\" is already owned, but doesn't list it", "purchase_failed"))
        })
    }

    fun owned(done: (Result<List<Purchase>>) -> Unit) = withClient(done) { current ->
        queryOwned(current, BillingClient.ProductType.INAPP) { inApp ->
            inApp.fold({ oneTime ->
                queryOwned(current, BillingClient.ProductType.SUBS) { subscriptions ->
                    done(subscriptions.map { oneTime + it })
                }
            }, { done(Result.failure(it)) })
        }
    }

    private fun queryOwned(current: BillingClient, type: String, done: (Result<List<Purchase>>) -> Unit) {
        val params = QueryPurchasesParams.newBuilder().setProductType(type).build()
        current.queryPurchasesAsync(params) { result, purchases ->
            MainThread.runOnMain {
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    purchases.filter { it.isAcknowledged }.forEach { acknowledged.add(it.purchaseToken) }
                    done(Result.success(purchases))
                } else {
                    done(Result.failure(billingError(result, "store_error")))
                }
            }
        }
    }

    fun finish(token: String, consume: Boolean, done: (Result<Unit>) -> Unit) = withClient(done) { current ->
        val answer = { result: BillingResult ->
            MainThread.runOnMain {
                if (result.responseCode == BillingClient.BillingResponseCode.OK) {
                    acknowledged.add(token)
                    done(Result.success(Unit))
                } else {
                    done(Result.failure(billingError(result, "store_error")))
                }
            }
        }
        when {
            consume -> current.consumeAsync(ConsumeParams.newBuilder().setPurchaseToken(token).build()) { result, _ -> answer(result) }
            token in acknowledged -> done(Result.success(Unit))
            else -> current.acknowledgePurchase(AcknowledgePurchaseParams.newBuilder().setPurchaseToken(token).build()) { answer(it) }
        }
    }

    // ------------------------------------------------------------------
    // Updates
    // ------------------------------------------------------------------

    fun subscribe() = MainThread.runOnMain {
        subscribed = true
        held.forEach(::emit)
        held.clear()
        refresh()
    }

    /** Pick up what's unacknowledged: a pending purchase that completed, or a purchase made outside the app. */
    fun refresh() = MainThread.runOnMain {
        if (!subscribed) return@runOnMain
        owned { found ->
            found.fold({ list -> list.filterNot { it.isAcknowledged }.forEach(::announce) }, {
                Log.w(PNBridge.TAG, "Purchases couldn't refresh: ${it.message}")
            })
        }
    }

    private fun announce(purchase: Purchase) {
        if (purchase.purchaseState != Purchase.PurchaseState.PURCHASED || !announced.add(purchase.purchaseToken)) return
        val update = wire(purchase)
        if (subscribed) emit(update) else held.add(update)
    }

    private fun emit(update: Wire) = ModuleEvents.emit("Purchases", "update", update.mapValues { it.value.nativeValue() })
}
