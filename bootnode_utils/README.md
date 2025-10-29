# Bootnode API

The Bootnode API provides controlled access for frontends (e.g., scanners, stats dashboards) to query the subnet bootnode list and heartbeats (i.e., the DHT Records `"nodes"` key).

<b>Do not give any party API access without trusting them.</b>

To prevent abuse, requests are rate-limited by both API key and IP address.

By default, each combination of API key and IP is limited to 5 requests per minute.

## API Keys

Each request requires a valid API key. API keys are managed locally and stored in bootnode_rest_keys.json.

#### Parameters

`owner` – Identifier for the owner of the API key
`key` – The API key string (generated if not provided)
`active` – Boolean flag indicating whether the key is enabled

##### Example
```bash
[
  { "owner": "party1", "key": "key-party1-abc123", "active": true },
  { "owner": "party2", "key": "key-party2-xyz456", "active": true },
  { "owner": "party3", "key": "key-party3-789qwe", "active": false }
]
```

## Managing API Keys

Keys can be manually added to the JSON file or by using the following CLI commands.

#### Add a new API key

Generates a new key for the given owner (unless one already exists):

```bash
mesh-add-api-key --owner <owner_name>
```
#### Deactivate an API key

Mark an owner's key as inactive without removing it:
```bash
mesh-add-api-key --owner <owner_name> --inactive
```
#### Reactivate an API key

Restore access for an owner's key:
```bash
mesh-add-api-key --owner <owner_name>
```

## Notes

By default keys are stored in `bootnode_rest_keys.json` or the directory of your choosing.

Updating a key will overwrite the existing one for that owner.

Only active keys are accepted by the API.