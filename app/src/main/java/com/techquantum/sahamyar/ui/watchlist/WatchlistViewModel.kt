package com.techquantum.sahamyar.ui.watchlist

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.techquantum.sahamyar.data.local.DatabaseProvider
import com.techquantum.sahamyar.data.local.entity.WatchlistEntity
import com.techquantum.sahamyar.data.repository.WatchlistRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

data class WatchlistAddResult(
    val insCode: String,
    val message: String,
    val success: Boolean
)

class WatchlistViewModel(application: Application) : AndroidViewModel(application) {

    private val _addResult = MutableStateFlow<WatchlistAddResult?>(null)
    val addResult: StateFlow<WatchlistAddResult?> = _addResult

    private val repository = WatchlistRepository(
        DatabaseProvider.get(application).watchlistDao()
    )

    val items = repository.observeItems().stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = emptyList()
    )

    fun addStock(
        insCode: String,
        symbol: String,
        companyName: String?,
        market: String?
    ) {
        viewModelScope.launch {
            runCatching {
                repository.addStock(insCode, symbol, companyName, market)
            }.onSuccess { id ->
                _addResult.value = if (id == -1L) {
                    WatchlistAddResult(insCode, "این نماد قبلاً در دیده‌بان است", false)
                } else {
                    WatchlistAddResult(insCode, "نماد به دیده‌بان اضافه شد", true)
                }
            }.onFailure {
                _addResult.value = WatchlistAddResult(
                    insCode, "افزودن نماد انجام نشد", false
                )
            }
        }
    }

    fun removeStock(item: WatchlistEntity) {
        viewModelScope.launch {
            repository.removeStock(item.id)
        }
    }

    suspend fun isTracked(insCode: String): Boolean {
        return repository.isTracked(insCode)
    }
}
