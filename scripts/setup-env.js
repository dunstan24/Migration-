const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const rootDir = path.resolve(__dirname, '..');
const frontendDir = path.join(rootDir, 'frontend');
const backendDir = path.join(rootDir, 'backend');

const rootEnvPath = path.join(rootDir, '.env');
const rootEnvExamplePath = path.join(rootDir, '.env.example');
const frontendEnvPath = path.join(frontendDir, '.env');
const backendEnvPath = path.join(backendDir, '.env');

function generateSecret() {
  return crypto.randomBytes(32).toString('hex');
}

function processEnvFile(filePath, examplePath) {
  let content = '';

  if (fs.existsSync(filePath)) {
    console.log(`[INFO] Reading existing ${filePath}`);
    content = fs.readFileSync(filePath, 'utf8');
  } else if (fs.existsSync(examplePath)) {
    console.log(`[INFO] Creating ${filePath} from example`);
    content = fs.readFileSync(examplePath, 'utf8');
  } else {
    console.error(`[ERROR] No .env or .env.example found at ${filePath}`);
    return null;
  }

  // Define secrets to generate and their placeholders
  const secrets = [
    { key: 'NEXTAUTH_SECRET', placeholder: 'generate_a_random_string_here' },
    { key: 'SECRET_KEY', placeholder: 'generate_a_random_string_here' },
    { key: 'REFRESH_SECRET_KEY', placeholder: 'generate_another_random_string_here' }
  ];

  let modified = false;
  secrets.forEach(({ key, placeholder }) => {
    const pattern = new RegExp(`^${key}=${placeholder}$`, 'm');
    if (pattern.test(content)) {
      console.log(`[OK] Generating secure ${key}...`);
      content = content.replace(pattern, `${key}=${generateSecret()}`);
      modified = true;
    } else if (!content.includes(`${key}=`)) {
      console.log(`[OK] Appending ${key}...`);
      content += `\n${key}=${generateSecret()}`;
      modified = true;
    }
  });

  // Also handle the generic old placeholder if present anywhere
  const oldPlaceholder = 'change-me-in-production';
  if (content.includes(oldPlaceholder)) {
    console.log(`[OK] Replacing legacy placeholders...`);
    content = content.split('\n').map(line => {
      if (line.includes(oldPlaceholder)) {
        const [varName] = line.split('=');
        return `${varName}=${generateSecret()}`;
      }
      return line;
    }).join('\n');
    modified = true;
  }

  if (modified || !fs.existsSync(filePath)) {
    fs.writeFileSync(filePath, content, 'utf8');
  }
  return content;
}

console.log('--- Environment Setup Automation ---');

// 1. Process root .env
const envContent = processEnvFile(rootEnvPath, rootEnvExamplePath);

// 2. Ensure frontend and backend see the variables
if (envContent) {
  console.log(`[INFO] Syncing configuration to frontend and backend...`);
  
  // Sync to frontend
  fs.writeFileSync(frontendEnvPath, envContent, 'utf8');
  console.log(`[OK] Synced to ${frontendEnvPath}`);

  // Sync to backend
  fs.writeFileSync(backendEnvPath, envContent, 'utf8');
  console.log(`[OK] Synced to ${backendEnvPath}`);
}

console.log('--- Setup Complete! ---');

