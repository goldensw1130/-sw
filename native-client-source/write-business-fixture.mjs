import {writeFileSync} from 'node:fs';
import {businessModules} from '../oreummok-cloud/service/business.mjs';
writeFileSync(process.argv[2],'package com.oreummok.nativeapp; class BusinessFixture {static final String DATA='+JSON.stringify(JSON.stringify(businessModules))+';}','utf8');
