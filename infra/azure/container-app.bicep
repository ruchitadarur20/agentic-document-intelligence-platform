param location string = resourceGroup().location
param appName string = 'agentic-doc-intel'
param image string

resource env 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: '${appName}-env'
  location: location
}

resource app 'Microsoft.App/containerApps@2023-05-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: env.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
      }
    }
    template: {
      containers: [
        {
          name: 'api'
          image: image
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
    }
  }
}

