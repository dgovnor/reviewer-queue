const { createApp, ref, onMounted } = Vue;

const ACTION_LABELS = {
  claim: "Claim",
  approve: "Approve",
  reject: "Reject",
  escalate: "Escalate",
};

async function jsonFetch(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = body.error || `Request failed (${res.status})`;
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return body;
}

createApp({
  setup() {
    const reviewer = ref("");
    const queue = ref([]);
    const selectedId = ref(null);
    const selected = ref(null);

    const loadingQueue = ref(false);
    const loadingDetail = ref(false);
    const actionInFlight = ref(false);

    const queueError = ref(null);
    const detailError = ref(null);
    const flash = ref(null);

    const formatDate = (iso) => {
      try {
        return new Date(iso).toLocaleString();
      } catch {
        return iso;
      }
    };

    const actionLabel = (action) => ACTION_LABELS[action] || action;

    const showFlash = (message, kind = "info") => {
      flash.value = { message, kind };
      setTimeout(() => {
        if (flash.value && flash.value.message === message) flash.value = null;
      }, 4000);
    };

    const loadReviewer = async () => {
      try {
        const data = await jsonFetch("/api/reviewer");
        reviewer.value = data.reviewer;
      } catch (err) {
        showFlash(`Failed to load reviewer: ${err.message}`, "error");
      }
    };

    const loadQueue = async () => {
      loadingQueue.value = true;
      queueError.value = null;
      try {
        queue.value = await jsonFetch("/api/items");
      } catch (err) {
        queueError.value = `Failed to load queue: ${err.message}`;
      } finally {
        loadingQueue.value = false;
      }
    };

    const loadDetail = async (id) => {
      loadingDetail.value = true;
      detailError.value = null;
      try {
        selected.value = await jsonFetch(`/api/items/${id}`);
      } catch (err) {
        detailError.value = `Failed to load item: ${err.message}`;
        selected.value = null;
      } finally {
        loadingDetail.value = false;
      }
    };

    const selectItem = (id) => {
      selectedId.value = id;
      loadDetail(id);
    };

    const performAction = async (action) => {
      if (!selected.value) return;
      actionInFlight.value = true;
      const itemId = selected.value.id;
      try {
        const updated = await jsonFetch(`/api/items/${itemId}/${action}`, {
          method: "POST",
        });
        selected.value = updated;
        showFlash(`${actionLabel(action)} succeeded for ${itemId}.`, "success");
        await loadQueue();
      } catch (err) {
        showFlash(`${actionLabel(action)} failed: ${err.message}`, "error");
        // Refresh so UI reflects authoritative server state.
        await loadDetail(itemId);
        await loadQueue();
      } finally {
        actionInFlight.value = false;
      }
    };

    onMounted(async () => {
      await Promise.all([loadReviewer(), loadQueue()]);
      if (queue.value.length > 0) {
        selectItem(queue.value[0].id);
      }
    });

    return {
      reviewer,
      queue,
      selectedId,
      selected,
      loadingQueue,
      loadingDetail,
      actionInFlight,
      queueError,
      detailError,
      flash,
      formatDate,
      actionLabel,
      selectItem,
      performAction,
    };
  },
}).mount("#app");
