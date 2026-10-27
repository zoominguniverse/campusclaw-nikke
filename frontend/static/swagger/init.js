window.addEventListener('DOMContentLoaded', () => {
  window.ui = SwaggerUIBundle({url: '/openapi.json', dom_id: '#swagger-ui', persistAuthorization: false,
    deepLinking: true, validatorUrl: null, supportedSubmitMethods: ['get', 'post', 'put', 'delete'],
    presets: [SwaggerUIBundle.presets.apis], layout: 'BaseLayout'});
});
