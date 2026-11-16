package com.techquantum.sahamyar.ui.market

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.techquantum.sahamyar.data.remote.model.StockSearchItem
import com.techquantum.sahamyar.data.repository.StockRepository
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class MarketSearchState(
    val query: String = "",
    val items: List<StockSearchItem> = emptyList(),
    val isLoading: Boolean = false,
    val error: String? = null
)

class MarketViewModel : ViewModel() {

    private val repository = StockRepository()

    private val _state = MutableStateFlow(MarketSearchState())
    val state: StateFlow<MarketSearchState> = _state.asStateFlow()

    private var searchJob: Job? = null
    private var searchId = 0L

    fun search(query: String) {
        searchJob?.cancel()
        val currentSearchId = ++searchId

        if (query.trim().length < 2) {
            _state.value = MarketSearchState(query = query)
            return
        }

        _state.value = MarketSearchState(
            query = query,
            isLoading = true,
            error = null
        )

        searchJob = viewModelScope.launch {
            delay(400)

            repository.searchStocks(query).fold(
                onSuccess = { response ->
                    if (currentSearchId != searchId) return@fold
                    _state.value = MarketSearchState(
                        query = query,
                        items = response.items
                    )
                },
                onFailure = { error ->
                    if (currentSearchId != searchId) return@fold
                    _state.value = MarketSearchState(
                        query = query,
                        error = error.message ?: "خطای نامشخص"
                    )
                }
            )
        }
    }
}
