<template>
  <v-container fluid class="dashboard-shell pa-6 pa-md-8">
    <div class="dashboard-hero d-flex align-center justify-space-between mb-7">
      <div>
        <div class="text-overline text-primary font-weight-bold mb-1">Operations centre</div>
        <h1 class="text-h4 text-md-h3 font-weight-bold">Biometric Operations</h1>
        <p class="text-medium-emphasis mb-0">Live platform health, throughput, and device support</p>
      </div>
      <v-chip class="status-chip" :color="connected ? 'success' : 'error'" variant="tonal" size="large">
        <v-icon start :icon="connected ? 'mdi-lan-connect' : 'mdi-lan-disconnect'" />
        {{ connected ? 'Live' : 'Reconnecting' }}
      </v-chip>
    </div>

    <v-row>
      <v-col v-for="metric in metricCards" :key="metric.key" cols="12" sm="6" lg="3">
        <v-card rounded="xl" elevation="0" class="metric-card h-100">
          <v-card-text class="d-flex align-center ga-4 pa-5">
            <v-avatar :color="metric.color" variant="tonal" size="54">
              <v-icon :icon="metric.icon" size="28" />
            </v-avatar>
            <div>
              <div class="text-caption text-medium-emphasis">{{ metric.label }}</div>
              <div class="text-h4 font-weight-bold mt-1">{{ metrics[metric.key] }}</div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row class="mt-2">
      <v-col cols="12" lg="7">
        <v-card rounded="xl" elevation="0" class="emulation-card h-100">
          <v-card-text class="pa-6">
            <div class="d-flex align-start justify-space-between ga-4 mb-5">
              <div>
                <div class="text-overline text-primary font-weight-bold">Device support</div>
                <h2 class="text-h5 font-weight-bold mb-1">PC device emulation</h2>
                <p class="text-body-2 text-medium-emphasis mb-0">Copy a device snapshot and troubleshoot it safely on your PC.</p>
              </div>
              <v-avatar color="primary" variant="tonal" size="48"><v-icon icon="mdi-monitor-dashboard" /></v-avatar>
            </div>

            <v-select
              v-model="selectedDeviceId"
              :items="deviceProfiles"
              item-title="name"
              item-value="id"
              label="Device to emulate"
              variant="outlined"
              density="comfortable"
              prepend-inner-icon="mdi-fingerprint"
              hide-details
              class="mb-4"
            />

            <div class="d-flex flex-wrap ga-3">
              <v-btn color="primary" variant="flat" prepend-icon="mdi-content-copy" @click="copyDeviceInfo">
                {{ copied ? 'Sandbox snapshot ready' : 'Clone live device' }}
              </v-btn>
              <v-btn color="primary" variant="tonal" prepend-icon="mdi-open-in-new" @click="openEmulation">
                Open emulation workspace
              </v-btn>
            </div>
            <v-alert v-if="emulationReady" type="success" variant="tonal" density="compact" class="mt-4 mb-0">
              Snapshot ready for <strong>{{ selectedDevice.name }}</strong>. Open the workspace on your PC to inspect logs, test commands, and replay sync requests.
            </v-alert>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" lg="5">
        <v-card rounded="xl" elevation="0" class="checklist-card h-100">
          <v-card-text class="pa-6">
            <div class="d-flex align-center justify-space-between mb-5">
              <div>
                <div class="text-overline text-medium-emphasis font-weight-bold">Troubleshooting</div>
                <h2 class="text-h6 font-weight-bold">Emulation checklist</h2>
              </div>
              <v-chip size="small" color="success" variant="tonal">{{ checklistProgress }}/3 ready</v-chip>
            </div>
            <div v-for="item in checklist" :key="item.label" class="check-row d-flex align-center ga-3 py-3">
              <v-icon :color="item.done ? 'success' : 'grey'" :icon="item.done ? 'mdi-check-circle' : 'mdi-circle-outline'" />
              <span :class="item.done ? '' : 'text-medium-emphasis'">{{ item.label }}</span>
            </div>
            <v-divider class="my-4" />
            <v-select v-model="emulationIssue" :items="emulationIssues" item-title="label" item-value="value" label="Issue scenario" variant="outlined" density="comfortable" hide-details class="mb-3" />
            <v-btn block color="secondary" variant="tonal" :loading="emulationRunning" :disabled="tcpState !== 'connected'" prepend-icon="mdi-bug-play" @click="runEmulation">Run issue emulation</v-btn>
            <v-alert v-if="emulationMessage" type="info" variant="tonal" density="compact" class="mt-3 mb-0">{{ emulationMessage }}</v-alert>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-card rounded="xl" elevation="0" class="tcp-card mt-5">
      <v-card-text class="pa-6">
        <div class="d-flex align-start justify-space-between ga-4 mb-5">
          <div>
            <div class="text-overline text-primary font-weight-bold">Remote access</div>
            <h2 class="text-h6 font-weight-bold mb-1">Connect to device over TCP</h2>
            <p class="text-body-2 text-medium-emphasis mb-0">Open a short-lived diagnostic session to test reachability before emulation.</p>
          </div>
          <v-chip :color="tcpState === 'connected' ? 'success' : tcpState === 'connecting' ? 'warning' : 'grey'" variant="tonal">
            <v-icon start :icon="tcpState === 'connected' ? 'mdi-lan-check' : 'mdi-lan'" />
            {{ tcpStateLabel }}
          </v-chip>
        </div>
        <v-row dense>
          <v-col cols="12" md="5"><v-text-field v-model="tcpHost" label="Device IP / hostname" variant="outlined" density="comfortable" hide-details /></v-col>
          <v-col cols="12" sm="5" md="2"><v-text-field v-model.number="tcpPort" label="TCP port" type="number" min="1" max="65535" variant="outlined" density="comfortable" hide-details /></v-col>
          <v-col cols="12" sm="7" md="5" class="d-flex align-center ga-3"><v-btn color="primary" :loading="tcpState === 'connecting'" :disabled="!tcpHost || !tcpPort" prepend-icon="mdi-connection" @click="connectToDevice">Test TCP connection</v-btn><v-btn v-if="tcpState === 'connected'" variant="text" color="error" @click="disconnectDevice">Disconnect</v-btn></v-col>
        </v-row>
        <v-alert v-if="tcpMessage" :type="tcpState === 'connected' ? 'success' : 'info'" variant="tonal" density="compact" class="mt-4 mb-0">{{ tcpMessage }}</v-alert>
      </v-card-text>
    </v-card>

    <v-alert v-if="errorMessage" type="warning" variant="tonal" class="mt-5" closable>
      {{ errorMessage }}
    </v-alert>
  </v-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'

const emit = defineEmits(['open-emulation'])

const props = defineProps({
  apiBaseUrl: { type: String, default: window.location.origin },
  accessToken: { type: String, default: () => localStorage.getItem('access_token') || '' },
})

const connected = ref(false)
const errorMessage = ref('')
const metrics = reactive({
  total_devices: 0,
  online_devices: 0,
  events_per_minute: 0,
  active_sync_jobs: 0,
})
const selectedDeviceId = ref('zkteco-01')
const copied = ref(false)
const emulationReady = ref(false)
const deviceProfiles = [
  { id: 'zkteco-01', name: 'Reception — ZKTeco K40', serial: 'ZK-K40-004281', protocol: 'ZKTeco / TCP' },
  { id: 'suprema-02', name: 'Warehouse — Suprema BioStation', serial: 'BS2-119842', protocol: 'Suprema / TCP' },
  { id: 'hikvision-03', name: 'Gate — Hikvision MinMoe', serial: 'HK-MN-772104', protocol: 'Hikvision / ISAPI' },
]
const selectedDevice = computed(() => deviceProfiles.find((device) => device.id === selectedDeviceId.value) || deviceProfiles[0])
const tcpHost = ref('192.168.1.50')
const tcpPort = ref(4370)
const tcpState = ref('idle')
const tcpMessage = ref('')
const emulationIssue = ref('healthy')
const emulationRunning = ref(false)
const emulationMessage = ref('')
const emulationIssues = [
  { label: 'Healthy session', value: 'healthy' },
  { label: 'Inject network latency (2s)', value: 'latency' },
  { label: 'Simulate offline device', value: 'offline' },
  { label: 'Return malformed response', value: 'malformed' },
]
const tcpStateLabel = computed(() => ({ idle: 'Not connected', connecting: 'Checking…', connected: 'TCP connected' }[tcpState.value]))
const checklist = computed(() => [
  { label: 'Device snapshot copied', done: copied.value },
  { label: 'Emulation workspace opened', done: emulationReady.value },
  { label: 'Connection profile validated', done: emulationReady.value },
])
const checklistProgress = computed(() => checklist.value.filter((item) => item.done).length)
let socket
let reconnectTimer
let reconnectDelay = 1000

const metricCards = computed(() => [
  { key: 'total_devices', label: 'Total devices', icon: 'mdi-devices', color: 'primary' },
  { key: 'online_devices', label: 'Online devices', icon: 'mdi-check-network', color: 'success' },
  { key: 'events_per_minute', label: 'Events / minute', icon: 'mdi-pulse', color: 'info' },
  { key: 'active_sync_jobs', label: 'Active sync jobs', icon: 'mdi-sync', color: 'warning' },
])

async function copyDeviceInfo() {
  let snapshotData = { ...selectedDevice.value, copied_at: new Date().toISOString() }
  if (tcpState.value === 'connected') {
    try {
      const response = await fetch(`${props.apiBaseUrl}/api/v1/devices/${selectedDevice.value.id}/clone`, {
        method: 'POST',
        headers: props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {},
      })
      if (response.ok) snapshotData = await response.json()
    } catch {
      // Keep the local profile as a fallback when the live clone endpoint is unavailable.
    }
  }
  const snapshot = JSON.stringify(snapshotData, null, 2)
  try {
    await navigator.clipboard?.writeText(snapshot)
  } catch {
    // Clipboard access can be unavailable in an embedded browser; the snapshot is still prepared for the workspace.
  }
  copied.value = true
  emulationReady.value = false
}

function openEmulation() {
  if (tcpState.value !== 'connected') {
    tcpMessage.value = 'Connect to the device before opening emulation.'
    return
  }
  copied.value = true
  emulationReady.value = true
  emit('open-emulation', selectedDevice.value)
}

async function connectToDevice() {
  tcpState.value = 'connecting'
  tcpMessage.value = `Testing ${tcpHost.value}:${tcpPort.value}…`
  emit('connect-tcp', { device: selectedDevice.value, host: tcpHost.value, port: tcpPort.value })
  try {
    const response = await fetch(`${props.apiBaseUrl}/api/v1/devices/${selectedDevice.value.id}/connect`, {
      method: 'POST',
      headers: props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {},
    })
    const result = await response.json()
    if (!response.ok || !result.connected) throw new Error(result.error || 'Device did not accept the TCP connection.')
    tcpState.value = 'connected'
    emulationReady.value = true
    tcpMessage.value = `Connected to ${result.host}:${result.port}. You can now copy the snapshot into emulation.`
  } catch (error) {
    tcpState.value = 'idle'
    tcpMessage.value = error instanceof Error ? error.message : 'TCP connection failed.'
  }
}

function disconnectDevice() {
  tcpState.value = 'idle'
  tcpMessage.value = 'Diagnostic TCP session closed.'
  emit('disconnect-tcp', selectedDevice.value)
  fetch(`${props.apiBaseUrl}/api/v1/devices/${selectedDevice.value.id}/disconnect`, { method: 'POST', headers: props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {} }).catch(() => {})
}

async function runEmulation() {
  emulationRunning.value = true
  emulationMessage.value = 'Running diagnostic scenario…'
  try {
    const response = await fetch(`${props.apiBaseUrl}/api/v1/devices/${selectedDevice.value.id}/emulate?issue=${encodeURIComponent(emulationIssue.value)}`, {
      method: 'POST',
      headers: props.accessToken ? { Authorization: `Bearer ${props.accessToken}` } : {},
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.detail || 'Emulation failed.')
    emulationMessage.value = result.message
    if (emulationIssue.value === 'offline') {
      tcpState.value = 'idle'
      emulationReady.value = false
    }
  } catch (error) {
    emulationMessage.value = error instanceof Error ? error.message : 'Emulation failed.'
  } finally {
    emulationRunning.value = false
  }
}

function connect() {
  if (!props.accessToken) {
    errorMessage.value = 'Sign in to view live dashboard metrics.'
    return
  }
  const url = new URL(props.apiBaseUrl)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/ws/dashboard'
  url.searchParams.set('token', props.accessToken)
  socket = new WebSocket(url)

  socket.onopen = () => {
    connected.value = true
    errorMessage.value = ''
    reconnectDelay = 1000
  }
  socket.onmessage = ({ data }) => {
    try {
      Object.assign(metrics, JSON.parse(data))
    } catch {
      errorMessage.value = 'The dashboard received an invalid metric update.'
    }
  }
  socket.onerror = () => { errorMessage.value = 'Live metrics are temporarily unavailable.' }
  socket.onclose = () => {
    connected.value = false
    reconnectTimer = window.setTimeout(connect, reconnectDelay)
    reconnectDelay = Math.min(reconnectDelay * 2, 30000)
  }
}

onMounted(connect)
onBeforeUnmount(() => {
  window.clearTimeout(reconnectTimer)
  if (socket) {
    socket.onclose = null
    socket.close()
  }
})
</script>

<style scoped>
.dashboard-shell {
  min-height: 100%;
  background: linear-gradient(145deg, #f8faff 0%, #f4f7fb 55%, #f9f7ff 100%);
}

.dashboard-hero {
  padding: 4px 2px;
}

.status-chip {
  font-weight: 650;
  letter-spacing: .1px;
}

.metric-card,
.emulation-card,
.checklist-card {
  border: 1px solid rgba(53, 72, 108, .08);
  box-shadow: 0 10px 28px rgba(46, 62, 92, .08) !important;
}

.metric-card {
  transition: transform .18s ease, box-shadow .18s ease;
}

.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 30px rgba(46, 62, 92, .13) !important;
}

.emulation-card {
  background: linear-gradient(135deg, #ffffff 0%, #f4f7ff 100%);
}

.checklist-card {
  background: rgba(255, 255, 255, .86);
}

.check-row {
  border-top: 1px solid rgba(53, 72, 108, .08);
  font-size: .92rem;
}
</style>
